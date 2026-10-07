"""Real PostgreSQL upload -> preparation -> indexing -> grounded chat checks."""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

from test_documents import DocumentTestCase
from test_preparation import text_pdf
from studymate.embeddings import EmbeddingIdentity, InputTooLong
from studymate.indexing import process_index_next, recover_indexes, sync_jobs
from studymate.rag import retrieve
from studymate.worker import process_next

IDENTITY = EmbeddingIdentity('embeddinggemma:300m', 'test-digest')


async def vectors(texts, **kwargs):
    return [[1.0, *([0.0] * 767)] for _ in texts]


class RetrievalIntegrationTests(DocumentTestCase):
    def setUp(self):
        super().setUp()
        self.worker = psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row)
        self.addCleanup(self.worker.close)

    def prepare(self, texts, name='study.pdf'):
        document_id = UUID(self.upload(text_pdf(texts), name).json()['id'])
        while process_next(self.worker):
            pass
        return document_id

    def index(self):
        sync_jobs(self.worker, IDENTITY)
        with patch('studymate.indexing.jobs.embed', side_effect=vectors), \
                patch('studymate.indexing.jobs.model_identity', AsyncMock(return_value=IDENTITY)):
            while asyncio.run(process_index_next(self.worker, IDENTITY)):
                pass

    def test_only_selected_pdfs_are_retrieved_and_citations_match_physical_pages(self):
        first = self.prepare(['Introduction', 'Photosynthesis uses sunlight.'], 'biology.pdf')
        second = self.prepare(['Private astronomy evidence.'], 'astronomy.pdf')
        self.index()
        rows = retrieve([first], IDENTITY, [1.0, *([0.0] * 767)], 'photosynthesis')
        self.assertTrue(rows)
        self.assertTrue(all(row['document_id'] == first for row in rows))
        self.assertTrue(any(row['page_number'] == 2 and 'Photosynthesis' in row['text'] for row in rows))
        with patch('studymate.rag.context.model_identity', AsyncMock(return_value=IDENTITY)), \
                patch('studymate.rag.context.embed', side_effect=vectors), \
                patch('studymate.chat.generate_answer', AsyncMock(return_value='Plants use sunlight [1].')):
            response = self.client.post('/api/chat', json={'question': 'Come funziona la fotosintesi?', 'document_ids': [str(first)]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['citations'][0]['document_id'], str(first))
        self.assertNotIn(str(second), str(response.json()))

    def test_all_sources_must_be_ready_and_wrong_digest_is_rejected(self):
        first = self.prepare(['Ready text'])
        self.index()
        second = self.prepare(['Pending text'])
        with self.assertRaises(HTTPException) as failure:
            retrieve([first, second], IDENTITY, [1.0] * 768, 'text')
        self.assertEqual(failure.exception.status_code, 409)
        self.assertEqual(failure.exception.detail['documents'][0]['id'], str(second))
        with self.assertRaises(HTTPException):
            retrieve([first], EmbeddingIdentity(IDENTITY.model, 'changed'), [1.0] * 768, 'text')

    def test_backfill_and_reprocessing_invalidate_index_only_on_publication(self):
        document_id = self.prepare(['Original text'])
        self.worker.execute('DELETE FROM document_indexes WHERE document_id = %s', (document_id,))
        self.index()
        before = retrieve([document_id], IDENTITY, [1.0] * 768, 'text')[0]['publication_id']
        self.client.post(f'/api/documents/{document_id}/prepare')
        self.assertEqual(retrieve([document_id], IDENTITY, [1.0] * 768, 'text')[0]['publication_id'], before)
        while process_next(self.worker):
            pass
        with self.assertRaises(HTTPException):
            retrieve([document_id], IDENTITY, [1.0] * 768, 'text')
        self.index()
        self.assertNotEqual(retrieve([document_id], IDENTITY, [1.0] * 768, 'text')[0]['publication_id'], before)

    def test_retry_recovery_and_atomic_visibility(self):
        document_id = self.prepare(['Evidence'])
        sync_jobs(self.worker, IDENTITY)
        with patch('studymate.indexing.jobs.embed', AsyncMock(side_effect=HTTPException(503, 'Unavailable'))):
            asyncio.run(process_index_next(self.worker, IDENTITY))
        state = self.worker.execute('SELECT * FROM document_indexes WHERE document_id = %s', (document_id,)).fetchone()
        self.assertEqual(state['status'], 'queued')
        self.assertEqual(state['attempts'], 1)
        self.worker.execute("UPDATE document_indexes SET status = 'processing' WHERE document_id = %s", (document_id,))
        recover_indexes(self.worker)
        async def inspect(texts, **kwargs):
            metadata = self.client.get('/api/documents').json()
            self.assertEqual(next(doc for doc in metadata if doc['id'] == str(document_id))['availability'], 'waiting')
            return await vectors(texts)
        with patch('studymate.indexing.jobs.embed', side_effect=inspect), \
                patch('studymate.indexing.jobs.model_identity', AsyncMock(return_value=IDENTITY)):
            asyncio.run(process_index_next(self.worker, IDENTITY))
        self.assertEqual(self.worker.execute('SELECT status FROM document_indexes WHERE document_id = %s',
            (document_id,)).fetchone()['status'], 'ready')

    def test_deletion_and_replacement_during_embedding_never_publish_stale_vectors(self):
        for replace in (False, True):
            document_id = self.prepare(['Evidence'])
            sync_jobs(self.worker, IDENTITY)
            async def interrupt(texts, **kwargs):
                if replace:
                    self.client.post(f'/api/documents/{document_id}/prepare')
                    while process_next(self.worker):
                        pass
                else:
                    self.client.delete(f'/api/documents/{document_id}')
                return await vectors(texts)
            with patch('studymate.indexing.jobs.embed', side_effect=interrupt), \
                    patch('studymate.indexing.jobs.model_identity', AsyncMock(return_value=IDENTITY)):
                asyncio.run(process_index_next(self.worker, IDENTITY))
            count = self.worker.execute('SELECT count(*) AS n FROM retrieval_units u JOIN document_indexes i ON i.id=u.index_id WHERE i.document_id=%s',
                (document_id,)).fetchone()['n']
            self.assertEqual(count, 0)

    def test_embedding_overflow_subdivides_without_losing_evidence(self):
        document_id = self.prepare(['Unique long evidence ' * 50])
        sync_jobs(self.worker, IDENTITY)
        async def small_window(texts, **kwargs):
            if any(len(text) > 200 for text in texts):
                raise InputTooLong()
            return await vectors(texts)
        with patch('studymate.indexing.jobs.embed', side_effect=small_window), \
                patch('studymate.indexing.jobs.model_identity', AsyncMock(return_value=IDENTITY)):
            asyncio.run(process_index_next(self.worker, IDENTITY))
        rows = self.worker.execute('SELECT u.text FROM retrieval_units u JOIN document_indexes i ON i.id=u.index_id WHERE i.document_id=%s',
            (document_id,)).fetchall()
        self.assertGreater(len(rows), 1)
        self.assertTrue(all(len(row['text']) <= 200 for row in rows))

    def test_model_change_requeues_without_reextracting_original_pages(self):
        document_id = self.prepare(['Original evidence'])
        self.index()
        publication = self.worker.execute('SELECT id FROM document_publications WHERE document_id = %s',
            (document_id,)).fetchone()['id']
        changed = EmbeddingIdentity(IDENTITY.model, 'new-digest')
        sync_jobs(self.worker, changed)
        state = self.worker.execute('SELECT * FROM document_indexes WHERE document_id = %s', (document_id,)).fetchone()
        self.assertEqual(state['status'], 'queued')
        self.assertEqual(state['digest'], 'new-digest')
        self.assertEqual(state['publication_id'], publication)
        self.assertEqual(self.worker.execute('SELECT count(*) AS n FROM retrieval_units WHERE index_id = %s',
            (state['id'],)).fetchone()['n'], 0)

    def test_failed_reprocessing_keeps_index_and_unusable_sources_are_rejected(self):
        document_id = self.prepare(['Retained evidence'])
        self.index()
        self.client.post(f'/api/documents/{document_id}/prepare')
        with patch('studymate.preparation.pipeline.extract_pages', side_effect=ValueError('failed extraction')):
            while process_next(self.worker):
                pass
        self.assertTrue(retrieve([document_id], IDENTITY, [1.0] * 768, 'evidence'))
        empty = self.prepare([''])
        with self.assertRaises(HTTPException) as failure:
            retrieve([document_id, empty], IDENTITY, [1.0] * 768, 'evidence')
        self.assertEqual(failure.exception.detail['documents'][0]['reason'], 'no_text')
        self.client.delete(f'/api/documents/{empty}')
        with self.assertRaises(HTTPException) as failure:
            retrieve([empty], IDENTITY, [1.0] * 768, 'evidence')
        self.assertEqual(failure.exception.status_code, 404)

    def test_invalid_embedding_fails_without_publishing_units(self):
        document_id = self.prepare(['Evidence'])
        sync_jobs(self.worker, IDENTITY)
        with patch('studymate.indexing.jobs.embed', AsyncMock(side_effect=HTTPException(502, 'The embedding model returned invalid vectors'))):
            asyncio.run(process_index_next(self.worker, IDENTITY))
        state = self.worker.execute('SELECT id, status FROM document_indexes WHERE document_id = %s', (document_id,)).fetchone()
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(self.worker.execute('SELECT count(*) AS n FROM retrieval_units WHERE index_id = %s',
            (state['id'],)).fetchone()['n'], 0)
