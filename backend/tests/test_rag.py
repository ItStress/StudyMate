import json
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from studymate.embeddings import DIMENSIONS, EmbeddingIdentity, InputTooLong, embed, model_identity
from studymate.indexing import split_units
from studymate.main import app
from studymate.rag import ABSTENTION, Citation, budget_context, fuse_results, prepare_context, validate_answer


def evidence(text="Plants convert sunlight into chemical energy.", page=2):
    return {'id': uuid4(), 'chunk_id': uuid4(), 'document_id': uuid4(), 'publication_id': uuid4(),
        'filename': 'biology.pdf', 'page_number': page, 'text': text}


class RagTests(unittest.TestCase):
    def test_fusion_rewards_agreement_deduplicates_and_limits_results(self):
        rows = [evidence(str(i)) for i in range(9)]
        duplicate = {**rows[1], 'id': uuid4()}
        result = fuse_results(rows, [rows[1], duplicate, rows[0]])
        self.assertEqual(result[0]['id'], rows[1]['id'])
        self.assertEqual(len(result), 6)
        self.assertEqual(len({(r['document_id'], r['text']) for r in result}), 6)

    def test_budget_drops_old_history_before_removing_whole_evidence(self):
        row = evidence('evidence ' * 100)
        context, history, citations = budget_context('Question', [{'role': 'user', 'content': 'old' * 6000}], [row])
        self.assertEqual(history, [])
        self.assertEqual(citations[0].excerpt, row['text'])
        self.assertEqual(json.loads(context)[0]['physical_page'], 2)
        context, _, citations = budget_context('Question', [], [evidence('x' * 20000)])
        self.assertEqual(json.loads(context), [])
        self.assertEqual(citations, [])

    def test_citations_are_server_owned_and_unknown_or_missing_labels_fail(self):
        _, _, citations = budget_context('Question', [], [evidence()])
        answer, used, grounded = validate_answer('Plants use sunlight [1].', citations)
        self.assertTrue(grounded)
        self.assertEqual(used, citations)
        for text in ['Invented [2].', 'No citation.', 'Combined [1, 2].', 'Leading zero [01].']:
            with self.assertRaises(HTTPException):
                validate_answer(text, citations)
        self.assertEqual(validate_answer(ABSTENTION + ' Le fonti non bastano.', citations),
            ('Le fonti non bastano.', [], False))
        with self.assertRaises(HTTPException):
            validate_answer(ABSTENTION + ' Missing evidence [1].', citations)

    def test_oversized_unicode_units_keep_content_and_table_headers(self):
        text = 'α😀' * 2000
        parts = split_units(text)
        self.assertEqual(''.join(parts), text)
        self.assertTrue(all(len(part.encode()) <= 1600 for part in parts))
        header = 'Description | Value'
        rows = [f'Item {i} | {i}' for i in range(300)]
        parts = split_units(header + '\n' + '\n'.join(rows), header=header)
        self.assertTrue(all(part.startswith(header + '\n') for part in parts))
        recovered = [row for part in parts for row in part.splitlines()[1:]]
        self.assertEqual(recovered, rows)


class EmbeddingTests(unittest.IsolatedAsyncioTestCase):
    async def test_prefixes_dimensions_and_no_truncation(self):
        requests = []
        def respond(request):
            payload = json.loads(request.content)
            requests.append(payload)
            return httpx.Response(200, json={'embeddings': [[1.0] * DIMENSIONS]})
        for query in (False, True):
            client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            with patch('studymate.embeddings.httpx.AsyncClient', return_value=client):
                await embed(['Test'], query=query)
        self.assertTrue(requests[0]['input'][0].startswith('title: none | text: '))
        self.assertTrue(requests[1]['input'][0].startswith('task: search result | query: '))
        self.assertFalse(requests[0]['truncate'])
        self.assertEqual(requests[0]['dimensions'], 768)

    async def test_rejects_wrong_dimensions_non_finite_zero_and_wrong_count(self):
        for vectors in [[], [[1]], [[0] * 768], [[float('nan')] * 768], [[True] * 768]]:
            # Mock response bytes allow nonfinite JSON to exercise defensive validation.
            client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(
                200, content=json.dumps({'embeddings': vectors}).encode())))
            with patch('studymate.embeddings.httpx.AsyncClient', return_value=client):
                with self.assertRaises(HTTPException) as failure:
                    await embed(['Test'])
                self.assertEqual(failure.exception.status_code, 502)

    async def test_overflow_is_explicit_and_digest_is_resolved(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(
            400, json={'error': 'input length exceeds maximum context length'})))
        with patch('studymate.embeddings.httpx.AsyncClient', return_value=client):
            with self.assertRaises(InputTooLong):
                await embed(['Test'])
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(
            200, json={'models': [{'name': 'embeddinggemma:300m', 'digest': 'sha256:test'}]})))
        with patch('studymate.embeddings.httpx.AsyncClient', return_value=client):
            self.assertEqual(await model_identity(), EmbeddingIdentity('embeddinggemma:300m', 'sha256:test'))

    async def test_followup_is_rewritten_and_only_selected_documents_are_retrieved(self):
        row = evidence()
        identity = EmbeddingIdentity('embeddinggemma:300m', 'digest')
        history = [{'role': 'user', 'content': 'Explain photosynthesis'}]
        with patch('studymate.rag.context.model_identity', AsyncMock(return_value=identity)), \
                patch('studymate.rag.context.validate_sources') as ready, \
                patch('studymate.rag.context.generate_answer', AsyncMock(return_value='How does photosynthesis work?')) as rewrite, \
                patch('studymate.rag.context.embed', AsyncMock(return_value=[[1] * 768])) as embedding, \
                patch('studymate.rag.context.retrieve', return_value=[row]) as search:
            _, _, citations = await prepare_context('How does it work?', history, [row['document_id']])
            ready.assert_called_once_with([row['document_id']], identity)
            self.assertEqual(rewrite.call_args.kwargs['history'], history)
            self.assertEqual(rewrite.call_args.kwargs['max_output_tokens'], 128)
            embedding.assert_awaited_once_with(['How does photosynthesis work?'], query=True)
            self.assertEqual(search.call_args.args[0], [row['document_id']])
            self.assertEqual(citations[0].document_id, row['document_id'])


class RagApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.row = evidence()
        self.context, self.history, self.citations = budget_context('Question', [], [self.row])
        self.payload = {'question': 'Explain photosynthesis', 'document_ids': [str(self.row['document_id'])]}
        self.preparation = patch('studymate.chat.prepare_context', AsyncMock(
            return_value=(self.context, self.history, self.citations)))
        self.preparation.start()
        self.addCleanup(self.preparation.stop)

    def test_both_endpoints_require_selected_sources(self):
        for endpoint in ['/api/chat', '/api/chat/stream']:
            for ids in [None, [], ['invalid']]:
                payload = {'question': 'Question'}
                if ids is not None:
                    payload['document_ids'] = ids
                self.assertEqual(self.client.post(endpoint, json=payload).status_code, 422)

    def test_nonstreaming_response_preserves_citation_provenance(self):
        with patch('studymate.chat.generate_answer', AsyncMock(return_value='Sunlight is converted [1].')):
            response = self.client.post('/api/chat', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['grounded'])
        self.assertEqual(response.json()['citations'][0], self.citations[0].model_dump(mode='json'))

    def test_unknown_citations_never_complete_and_abstention_is_success(self):
        for answer, status in [('Invented [8]', 502), ('No citations', 502),
                (ABSTENTION + ' Not enough evidence.', 200)]:
            with patch('studymate.chat.generate_answer', AsyncMock(return_value=answer)):
                response = self.client.post('/api/chat', json=self.payload)
            self.assertEqual(response.status_code, status)
            if status == 200:
                self.assertFalse(response.json()['grounded'])
                self.assertEqual(response.json()['citations'], [])

    def test_stream_validates_done_and_hides_split_abstention_marker(self):
        for text, expected in [('Plants [1]', 'done'), ('Invented [8]', 'error'),
                (ABSTENTION + ' Non ci sono prove.', 'done')]:
            async def stream(*args, **kwargs):
                for character in text:
                    yield {'type': 'delta', 'content': character}
                yield {'type': 'done'}
            with patch('studymate.chat.stream_answer', side_effect=stream):
                response = self.client.post('/api/chat/stream', json=self.payload)
            events = [json.loads(line) for line in response.text.splitlines()]
            self.assertEqual(events[-1]['type'], expected)
            visible = ''.join(event.get('content', '') for event in events)
            self.assertNotIn(ABSTENTION, visible)
            if text.startswith(ABSTENTION):
                self.assertFalse(events[-1]['grounded'])
                self.assertIn('Non ci sono prove.', visible)

    def test_unavailable_sources_fail_before_streaming_headers(self):
        for status in [404, 409]:
            with patch('studymate.chat.prepare_context', AsyncMock(side_effect=HTTPException(
                    status, {'message': 'Unavailable PDFs', 'documents': [{'id': str(self.row['document_id'])}]}))):
                response = self.client.post('/api/chat/stream', json=self.payload)
            self.assertEqual(response.status_code, status)
            self.assertIn('documents', response.json()['detail'])
