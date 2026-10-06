import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from studymate.llm import STUDY_SYSTEM_PROMPT, StreamingAnswerFilter, stream_answer
from studymate.main import app


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, events, failure=None):
        self.events = events
        self.failure = failure
        self.closed = False

    async def __aiter__(self):
        for event in self.events:
            data = (json.dumps(event, ensure_ascii=False) + '\n').encode()
            # Exercise transport boundaries, including multibyte characters.
            for start in range(0, len(data), 7):
                yield data[start:start + 7]
        if self.failure:
            raise self.failure

    async def aclose(self):
        self.closed = True


def chunk(content='', done=False, **message):
    return {'message': {'content': content, **message}, 'done': done}


async def prepared_context(question, history, document_ids):
    return None, history[-20:], []


class ChatStreamTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.environment = patch.dict(os.environ, {'OLLAMA_CHAT_MODEL': 'test-model'})
        self.environment.start()
        self.preparation = patch('studymate.chat.prepare_context', side_effect=prepared_context)
        self.validation = patch('studymate.chat.validate_answer', side_effect=lambda answer, _: (answer, [], False))
        self.preparation.start()
        self.validation.start()

    def tearDown(self):
        self.environment.stop()
        self.preparation.stop()
        self.validation.stop()

    def request(self, transport, **payload):
        client = httpx.AsyncClient(transport=transport)
        with patch('studymate.llm.httpx.AsyncClient', return_value=client):
            response = self.client.post('/api/chat/stream', json={'document_ids': ['00000000-0000-0000-0000-000000000001'], 'question': 'Explain gravity', **payload})
        return response, [json.loads(line) for line in response.text.splitlines()]

    def test_streams_answer_in_order_and_forwards_history(self):
        history = [{'role': role, 'content': str(i)} for i in range(12) for role in ('user', 'assistant')]
        stream = ChunkStream([chunk('<answer>Gravità '), chunk('attracts mass.</answer>', True)])

        def respond(request):
            payload = json.loads(request.content)
            self.assertTrue(payload['stream'])
            self.assertFalse(payload['think'])
            self.assertEqual(payload['messages'][1:-1], history[-20:])
            self.assertEqual(payload['messages'][-1]['content'], 'Explain gravity')
            self.assertIn('Answer only from the supplied PDF evidence', payload['messages'][0]['content'])
            return httpx.Response(200, stream=stream)

        response, events = self.request(httpx.MockTransport(respond), history=history)
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/x-ndjson', response.headers['content-type'])
        self.assertEqual(events, [
            {'type': 'delta', 'content': 'Gravità '},
            {'type': 'delta', 'content': 'attracts mass.'}, {'type': 'done', 'citations': [], 'grounded': False},
        ])
        self.assertTrue(stream.closed)

    def test_filters_split_thinking_and_answer_tags(self):
        parts = ['<thi', 'nk>private<think>nested</think>', '</thi', 'nk><ans', 'wer>Ciao ', '😊</ans', 'wer>']
        stream = ChunkStream([chunk(part, i == len(parts) - 1, thinking='private') for i, part in enumerate(parts)])
        _, events = self.request(httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)))
        self.assertEqual(''.join(event.get('content', '') for event in events), 'Ciao 😊')
        self.assertEqual(events[-1], {'type': 'done', 'citations': [], 'grounded': False})

    def test_buffers_legacy_implicit_thinking_until_final_answer(self):
        answer_filter = StreamingAnswerFilter()
        self.assertEqual(answer_filter.feed('Private reasoning'), '')
        self.assertEqual(answer_filter.feed('</think>\nCiao!'), '')
        self.assertEqual(answer_filter.feed('', final=True), 'Ciao!')

    def test_fallback_for_model_without_answer_marker(self):
        stream = ChunkStream([chunk('Plain '), chunk('answer', True)])
        _, events = self.request(httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)))
        self.assertEqual(events, [{'type': 'delta', 'content': 'Plain answer'}, {'type': 'done', 'citations': [], 'grounded': False}])

    def test_does_not_expose_implicit_reasoning_before_answer_marker(self):
        answer_filter = StreamingAnswerFilter()
        self.assertEqual(answer_filter.feed('Private reasoning</think><ans'), '')
        self.assertEqual(answer_filter.feed('wer>Visible'), 'Visible')
        self.assertEqual(answer_filter.feed('</answer>', final=True), '')

    def test_implicit_thinking_quoting_answer_markers_does_not_leak_or_fail(self):
        parts = [
            'I need to use ', '<ans', 'wer> and </ans',
            'wer> tags. Explain the war.', '</thi',
            'nk>\n<ans', 'wer>World War II ', 'lasted from 1939 to 1945.</answer>',
        ]
        stream = ChunkStream([chunk(part, i == len(parts) - 1) for i, part in enumerate(parts)])
        _, events = self.request(httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)))
        self.assertEqual(events, [
            {'type': 'delta', 'content': 'World War II '},
            {'type': 'delta', 'content': 'lasted from 1939 to 1945.'},
            {'type': 'done', 'citations': [], 'grounded': False},
        ])

    def test_quoted_markers_in_implicit_thinking_without_final_marker_use_fallback(self):
        answer_filter = StreamingAnswerFilter()
        self.assertEqual(answer_filter.feed('Use <answer> and </answer> tags.'), '')
        self.assertEqual(answer_filter.feed('</think>World War II lasted from 1939 to 1945.'), '')
        self.assertEqual(answer_filter.feed('', final=True), 'World War II lasted from 1939 to 1945.')

    def test_markers_quoted_inside_explicit_thinking_are_ignored(self):
        answer_filter = StreamingAnswerFilter()
        self.assertEqual(answer_filter.feed('<think>Use <answer> and </answer> tags.</think>'), '')
        self.assertEqual(answer_filter.feed('<answer>Visible text'), 'Visible text')
        self.assertEqual(answer_filter.feed('</answer>', final=True), '')

    def test_answer_marker_after_leading_whitespace_streams_without_waiting_for_done(self):
        answer_filter = StreamingAnswerFilter()
        self.assertEqual(answer_filter.feed('\n  <ans'), '')
        self.assertEqual(answer_filter.feed('wer>First part'), 'First part')
        self.assertEqual(answer_filter.feed(' second part</answer>', final=True), ' second part')

    def test_timeout_and_connection_errors(self):
        for exception, status in [(httpx.ConnectError('secret'), 503), (httpx.ReadTimeout('secret'), 504)]:
            with self.subTest(status=status):
                def fail(_):
                    raise exception
                _, events = self.request(httpx.MockTransport(fail))
                self.assertEqual(events[0]['status'], status)
                self.assertNotIn('secret', str(events))

    def test_timeout_after_partial_answer_closes_connection(self):
        stream = ChunkStream([chunk('<answer>Partial')], httpx.ReadTimeout('secret'))
        _, events = self.request(httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)))
        self.assertEqual(events[0], {'type': 'delta', 'content': 'Partial'})
        self.assertEqual(events[-1]['status'], 504)
        self.assertTrue(stream.closed)

    def test_invalid_or_incomplete_stream_never_completes(self):
        cases = [[], [chunk('<answer>Partial')], [chunk('<think>Only reasoning</think>', True)],
                 [{'message': {'content': 42}, 'done': True}], [{'error': 'secret'}]]
        for events in cases:
            with self.subTest(events=events):
                stream = ChunkStream(events)
                _, result = self.request(httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)))
                self.assertEqual(result[-1]['type'], 'error')
                self.assertEqual(result[-1]['status'], 502)
                self.assertNotIn({'type': 'done', 'citations': [], 'grounded': False}, result)

    def test_upstream_http_error(self):
        _, events = self.request(httpx.MockTransport(lambda _: httpx.Response(404, text='secret')))
        self.assertEqual(events, [{'type': 'error', 'status': 502, 'detail': 'The language model returned an error'}])

    def test_blank_question_and_invalid_role(self):
        for payload in [{'question': '  '}, {'question': 'Hello', 'history': [{'role': 'system', 'content': 'secret'}]}]:
            self.assertEqual(self.client.post('/api/chat/stream', json=payload).status_code, 422)

    def test_missing_model_configuration(self):
        with patch.dict(os.environ, {'OLLAMA_CHAT_MODEL': ''}):
            response = self.client.post('/api/chat/stream', json={'document_ids': ['00000000-0000-0000-0000-000000000001'], 'question': 'Hello'})
        self.assertEqual(json.loads(response.text)['status'], 503)

    def test_study_prompt_is_honest_about_pdf_access(self):
        self.assertIn("language of the user's question", STUDY_SYSTEM_PROMPT)
        self.assertIn('Conversation history is not evidence', STUDY_SYSTEM_PROMPT)
        self.assertIn('Never invent citations', STUDY_SYSTEM_PROMPT)
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok'})


class StreamCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelling_iterator_closes_upstream_and_does_not_finish_exchange(self):
        stream = ChunkStream([chunk('<answer>First'), chunk('Second</answer>', True)])
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)))
        with patch.dict(os.environ, {'OLLAMA_CHAT_MODEL': 'test-model'}), patch(
            'studymate.llm.httpx.AsyncClient', return_value=client
        ):
            events = stream_answer('Explain gravity')
            self.assertEqual(await anext(events), {'type': 'delta', 'content': 'First'})
            self.assertFalse(stream.closed)
            await events.aclose()
        self.assertTrue(stream.closed)
        self.assertTrue(client.is_closed)
