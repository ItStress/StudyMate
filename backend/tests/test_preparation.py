import unittest
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from studymate.preparation import normalize_text, split_chunks
from studymate.database import connection
from studymate.migrations import MIGRATIONS, migrate
from studymate.worker import acquire_lock, process_next, recover_interrupted
from test_documents import DocumentTestCase, sample_pdf
from pdf_fixtures import geometry_pdf, line


def text_pdf(texts: list[str]) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    font_ref = writer._add_object(font)
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): font_ref})})
        stream = DecodedStreamObject()
        escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream.set_data(f'BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


class ChunkTests(unittest.TestCase):
    def test_normalization_preserves_paragraphs_and_content(self) -> None:
        self.assertEqual(normalize_text('  Hello\t world\r\n\r\n\r\nA\x00 formula: x + y\rhy-\rphen  '),
            'Hello world\n\nA formula: x + y\nhy-\nphen')

    def test_empty_and_short_text(self) -> None:
        self.assertEqual(split_chunks(''), [])
        self.assertEqual(split_chunks('Short text'), [(0, 10, 'Short text')])

    def test_unicode_offsets_overlap_and_coverage(self) -> None:
        for text in ['a' * 6300, 'Study café 😀 formula α. ' * 500,
                     ('Paragraph of study notes. ' * 30 + '\n\n') * 20]:
            with self.subTest(text=text[:20]):
                chunks = split_chunks(text)
                covered = set()
                for start, end, passage in chunks:
                    self.assertEqual(passage, text[start:end])
                    self.assertTrue(0 < len(passage) <= 2000)
                    covered.update(range(start, end))
                self.assertEqual(len({(s, e) for s, e, _ in chunks}), len(chunks))
                self.assertTrue(all(i in covered for i, char in enumerate(text) if not char.isspace()))
                for previous, following in zip(chunks, chunks[1:]):
                    self.assertGreater(following[1], previous[1])
                    self.assertLessEqual(following[0], previous[1])
                    self.assertLessEqual(previous[1] - following[0], 200)

    def test_paragraph_then_word_boundaries(self) -> None:
        text = 'a' * 800 + '\n\n' + 'b' * 1500
        self.assertEqual(split_chunks(text)[0][1], 800)
        self.assertEqual(split_chunks('word ' * 600)[0][1] % 5, 4)

    def test_exact_overlap_and_invalid_settings(self) -> None:
        chunks = split_chunks('x' * 4001)
        self.assertEqual(chunks[0][:2], (0, 2000))
        self.assertEqual(chunks[1][:2], (1800, 3800))
        with self.assertRaises(ValueError):
            split_chunks('text', size=200, overlap=200)


class PreparationApiTests(DocumentTestCase):
    def test_image_storage_failure_keeps_text_without_a_dangling_image(self) -> None:
        document_id = self.upload(text_pdf(['Useful evidence'])).json()['id']
        with patch('PIL.Image.Image.save', side_effect=OSError('image storage unavailable')):
            self.drain()
        page = self.client.get(f'/api/documents/{document_id}/pages').json()['items'][0]
        self.assertEqual(page['text'], 'Useful evidence')
        self.assertIsNone(page['page_image_id'])
        self.assertTrue(any('render' in warning.lower() for warning in page['warnings']))

    def test_equation_visual_region_preserves_a_stacked_fraction(self) -> None:
        commands = line('E =', 72, 700) + line('2', 105, 711, 8) + line('4', 105, 689, 8)
        commands += '103 703 m 114 703 l S\n'
        document_id = self.upload(geometry_pdf([commands])).json()['id']
        self.drain()
        page = self.client.get(f'/api/documents/{document_id}/pages').json()['items'][0]
        equation = next(block for block in page['blocks'] if block['kind'] == 'equation')
        self.assertIn('2', equation['text'])
        self.assertIn('4', equation['text'])
        self.assertLessEqual(equation['bbox'][1], 75)
        self.assertGreaterEqual(equation['bbox'][3], 104)
        self.assertTrue(equation['asset_id'])

    def test_plain_text_chunk_references_only_overlapping_evidence(self) -> None:
        commands = ''.join(line(f'Independent narrative {chr(65 + index % 26)} ' + 'contextual evidence ' * 6,
            40, 760 - index * 11, 5) for index in range(60))
        document_id = self.upload(geometry_pdf([commands])).json()['id']
        self.drain()
        page = self.client.get(f'/api/documents/{document_id}/pages').json()['items'][0]
        chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()['items']
        self.assertGreater(len(chunks), 1)
        included = [block for block in page['blocks'] if not block['excluded']]
        self.assertIn(included[0]['id'], chunks[0]['content_refs'])
        self.assertNotIn(included[-1]['id'], chunks[0]['content_refs'])

    def test_mixed_pages_keep_neighboring_prose_in_normal_passages(self) -> None:
        commands = ''.join(line(f'Important evidence paragraph {chr(65 + index)} explanatory sentence.', 72, 730 - index * 13, 9)
            for index in range(20)) + line('E = m c', 72, 430)
        document_id = self.upload(geometry_pdf([commands])).json()['id']
        self.drain()
        chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()['items']
        prose = [chunk for chunk in chunks if 'Important evidence' in chunk['text']]
        self.assertEqual(len(prose), 1)
        self.assertIn('paragraph A', prose[0]['text'])
        self.assertIn('paragraph T', prose[0]['text'])
        self.assertEqual(len(prose[0]['content_refs']), 20)

    def test_failed_visual_only_rerun_retains_its_previous_evidence(self) -> None:
        document_id = self.upload(geometry_pdf(['72 600 80 60 re S\n'])).json()['id']
        self.drain()
        before = self.client.get(f'/api/documents/{document_id}/pages').json()
        self.assertEqual(before['published']['chunk_count'], 0)
        self.assertTrue(before['items'][0]['page_image_id'])
        self.client.post(f'/api/documents/{document_id}/prepare')
        with patch('pdfplumber.page.Page.to_image', side_effect=ValueError('rendering unavailable')):
            self.drain()
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'failed')
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages').json(), before)

    def test_equation_crop_includes_raised_symbols(self) -> None:
        commands = line('E = m c', 72, 700) + line('2', 115, 711, 8)
        document_id = self.upload(geometry_pdf([commands])).json()['id']
        self.drain()
        page = self.client.get(f'/api/documents/{document_id}/pages').json()['items'][0]
        equation = next(block for block in page['blocks'] if block['kind'] == 'equation')
        self.assertIn('2', equation['text'])
        self.assertLessEqual(equation['bbox'][1], 75)
        self.assertGreaterEqual(equation['bbox'][2], 119)
        self.assertFalse(any(block['kind'] == 'text' and block['text'] == '2' for block in page['blocks']))

    def test_oversized_tables_split_by_rows_and_repeat_headers(self) -> None:
        count = 55
        bottom = 730 - (count + 1) * 10
        commands = ''.join(f'{x} {bottom} m {x} 730 l S\n' for x in [72, 400, 540])
        commands += ''.join(f'72 {730 - index * 10} m 540 {730 - index * 10} l S\n'
            for index in range(count + 2))
        commands += line('Description', 80, 722, 7) + line('Value', 410, 722, 7)
        for index in range(count):
            commands += line(f'Measurement {index:02d} with additional experimental context', 80, 712 - index * 10, 7)
            commands += line(str(index), 410, 712 - index * 10, 7)
        document_id = self.upload(geometry_pdf([commands])).json()['id']
        self.drain()
        chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()['items']
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk['text'].startswith('Description | Value\n') for chunk in chunks))
        self.assertEqual(sum(len(chunk['text'].splitlines()) - 1 for chunk in chunks), count)
        self.assertTrue(all(chunk['start_offset'] is None and chunk['content_refs'] for chunk in chunks))
        self.assertTrue(all(len(chunk['text']) <= 2000 for chunk in chunks))

    def test_unruled_numeric_table_preserves_cell_relationships(self) -> None:
        commands = (line('Quantity', 72, 700) + line('Value', 300, 700)
            + line('Mass', 72, 675) + line('12', 300, 675)
            + line('Speed', 72, 650) + line('34', 300, 650)
            + line('Time', 72, 625) + line('56', 300, 625))
        document_id = self.upload(geometry_pdf([commands])).json()['id']
        self.drain()
        page = self.client.get(f'/api/documents/{document_id}/pages').json()['items'][0]
        tables = [block for block in page['blocks'] if block['kind'] == 'table']
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]['rows'], [['Quantity', 'Value'], ['Mass', '12'], ['Speed', '34'], ['Time', '56']])

    def test_page_requests_reject_a_replaced_publication(self) -> None:
        document_id = self.upload(text_pdf(['Evidence'])).json()['id']
        self.drain()
        published = self.metadata(document_id)['published']['id']
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages?publication_id={published}').status_code, 200)
        self.client.post(f'/api/documents/{document_id}/prepare')
        self.drain()
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages?publication_id={published}').status_code, 409)

    def test_failed_reprocessing_retains_published_pages_and_images(self) -> None:
        document_id = self.upload(text_pdf(['Retained evidence'])).json()['id']
        self.drain()
        before = self.client.get(f'/api/documents/{document_id}/pages').json()
        image_id = before['items'][0]['page_image_id']
        self.assertEqual(self.client.post(f'/api/documents/{document_id}/prepare').status_code, 202)
        with patch('pdfplumber.open', side_effect=ValueError('unreadable PDF')):
            self.drain()
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'failed')
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages').json(), before)
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/assets/{image_id}').status_code, 200)
        self.assertEqual(self.client.post(f'/api/documents/{document_id}/prepare').status_code, 202)
        self.drain()
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/assets/{image_id}').status_code, 404)

    def test_bitmap_and_vector_diagrams_keep_captions_and_warn_on_uncertainty(self) -> None:
        bitmap = 'q 80 0 0 60 72 600 cm /Im1 Do Q\n' + line('Figure 1: Process', 72, 580)
        vector = '72 600 80 60 re S\n152 630 m 210 630 l S\n' + line('Figure 2: Flow', 72, 580)
        uncertain = '72 600 80 60 re S\n'
        document_id = self.upload(geometry_pdf([bitmap, vector, uncertain], bitmap=True)).json()['id']
        self.drain()
        pages = self.client.get(f'/api/documents/{document_id}/pages').json()['items']
        for page, caption in zip(pages[:2], ['Figure 1: Process', 'Figure 2: Flow']):
            diagrams = [block for block in page['blocks'] if block['kind'] == 'diagram']
            self.assertEqual(len(diagrams), 1)
            self.assertEqual(diagrams[0]['caption'], caption)
            image = self.client.get(f"/api/documents/{document_id}/assets/{diagrams[0]['asset_id']}")
            self.assertEqual(image.status_code, 200)
            self.assertTrue(image.content.startswith(b'\x89PNG'))
            chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()['items']
            self.assertTrue(any(diagrams[0]['id'] in chunk['content_refs'] and caption == chunk['text']
                for chunk in chunks))
        self.assertTrue(any('caption' in warning.lower() for warning in pages[2]['warnings']))
        self.assertTrue(pages[2]['page_image_id'])

    def test_equation_text_has_visual_evidence_and_chunk_links(self) -> None:
        document_id = self.upload(geometry_pdf([line('Energy equation', 72, 740)
            + line('E = m c', 72, 700)])).json()['id']
        self.drain()
        page = self.client.get(f'/api/documents/{document_id}/pages').json()['items'][0]
        equations = [block for block in page['blocks'] if block['kind'] == 'equation']
        self.assertEqual(len(equations), 1)
        self.assertEqual(equations[0]['text'], 'E = m c')
        self.assertTrue(equations[0]['asset_id'])
        image = self.client.get(f"/api/documents/{document_id}/assets/{equations[0]['asset_id']}")
        self.assertEqual(image.status_code, 200)
        chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()['items']
        self.assertTrue(any(equations[0]['id'] in chunk['content_refs']
            and chunk['text'] == 'E = m c' for chunk in chunks))
        self.assertTrue(any('equation' in warning.lower() for warning in page['warnings']))

    def test_tables_preserve_rows_page_portions_and_chunk_evidence(self) -> None:
        commands = ''.join(f'{x} 600 m {x} 675 l S\n' for x in [72, 210, 350])
        commands += ''.join(f'72 {y} m 350 {y} l S\n' for y in [600, 625, 650, 675])
        commands += (line('Name', 80, 657) + line('Value', 220, 657)
            + line('Mass', 80, 632) + line('12', 220, 632)
            + line('Speed', 80, 607) + line('34', 220, 607))
        document_id = self.upload(geometry_pdf([commands, commands])).json()['id']
        self.drain()
        pages = self.client.get(f'/api/documents/{document_id}/pages').json()['items']
        for number, page in enumerate(pages, 1):
            tables = [block for block in page['blocks'] if block['kind'] == 'table']
            self.assertEqual(len(tables), 1)
            self.assertEqual(tables[0]['rows'], [['Name', 'Value'], ['Mass', '12'], ['Speed', '34']])
            self.assertEqual(page['page_number'], number)
            chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()['items']
            self.assertTrue(any(tables[0]['id'] in chunk['content_refs']
                and chunk['page_number'] == number for chunk in chunks))

    def test_layout_orders_columns_and_retains_excluded_margin_evidence(self) -> None:
        commands = (line('Repeated study header', 72, 770) + line('Left first', 72, 700)
            + line('Right first', 340, 700) + line('Left second', 72, 670)
            + line('Right second', 340, 670))
        document_id = self.upload(geometry_pdf([commands, commands])).json()['id']
        self.drain()
        page = self.client.get(f'/api/documents/{document_id}/pages').json()['items'][0]
        self.assertEqual(page['text'], 'Left first\nLeft second\nRight first\nRight second')
        self.assertTrue(any(block['excluded'] and block['text'] == 'Repeated study header'
            for block in page['blocks']))
        self.assertEqual(page['page_number'], 1)
        self.assertTrue(page['page_image_id'])
        image = self.client.get(f"/api/documents/{document_id}/assets/{page['page_image_id']}")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers['content-type'], 'image/png')
        self.assertTrue(image.content.startswith(b'\x89PNG'))
        chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()['items']
        self.assertFalse(any('Repeated study header' in chunk['text'] for chunk in chunks))

    def test_reprocessing_keeps_published_results_until_replacement(self) -> None:
        document_id = self.upload(text_pdf(['Original evidence'])).json()['id']
        self.drain()
        before = self.client.get(f'/api/documents/{document_id}/pages').json()
        requested = self.client.post(f'/api/documents/{document_id}/prepare')
        self.assertEqual(requested.status_code, 202)
        self.assertEqual(requested.json()['published'], before['published'])
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages').json(), before)
        self.assertEqual(self.client.post(f'/api/documents/{document_id}/prepare').status_code, 409)
        self.drain()
        after = self.client.get(f'/api/documents/{document_id}/pages').json()
        self.assertEqual(after['items'][0]['text'], before['items'][0]['text'])
        self.assertNotEqual(after['published']['id'], before['published']['id'])

    def test_published_page_results_identify_the_extraction(self) -> None:
        uploaded = self.upload(text_pdf(['Study notes', '']))
        document_id = uploaded.json()['id']
        self.assertIsNone(uploaded.json()['published'])
        self.drain()
        published = self.metadata(document_id)['published']
        self.assertEqual(published['pipeline_version'], '2')
        self.assertEqual(published['empty_pages'], [2])
        result = self.client.get(f'/api/documents/{document_id}/pages?offset=1&limit=1').json()
        self.assertEqual(result['published'], published)
        self.assertEqual(result['items'][0]['page_number'], 2)
        self.assertEqual(result['items'][0]['text'], '')
        self.assertFalse(result['items'][0]['has_text'])

    def setUp(self) -> None:
        super().setUp()
        self.worker = psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row)
        if not acquire_lock(self.worker):
            self.worker.close()
            super().tearDown()
            self.fail('A worker is already using the test database')

    def tearDown(self) -> None:
        self.worker.close()
        super().tearDown()

    def metadata(self, document_id: str) -> dict:
        return next(d for d in self.client.get('/api/documents').json() if d['id'] == document_id)

    def drain(self) -> None:
        while process_next(self.worker):
            pass

    def test_prepares_text_and_page_references(self) -> None:
        uploaded = self.upload(text_pdf(['Study notes ' * 400, 'Second page']))
        self.assertEqual(uploaded.status_code, 201)
        document_id = uploaded.json()['id']
        self.assertEqual(uploaded.json()['preparation']['status'], 'queued')
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/chunks').status_code, 409)
        self.assertEqual(self.client.post(f'/api/documents/{document_id}/prepare').status_code, 409)
        self.drain()
        preparation = self.metadata(document_id)['preparation']
        self.assertEqual(preparation['status'], 'ready')
        self.assertEqual(preparation['pages_processed'], 2)
        pages = self.client.get(f'/api/documents/{document_id}/pages').json()['items']
        chunks = self.client.get(f'/api/documents/{document_id}/chunks').json()
        self.assertEqual(chunks['total'], preparation['chunk_count'])
        for chunk in chunks['items']:
            page = pages[chunk['page_number'] - 1]
            self.assertEqual(chunk['document_id'], document_id)
            self.assertEqual(chunk['text'], page['text'][chunk['start_offset']:chunk['end_offset']])
        result = self.client.get(f'/api/documents/{document_id}/chunks?offset=1&limit=1').json()
        self.assertEqual(result['items'], chunks['items'][1:2])
        self.assertEqual(result['total'], chunks['total'])
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages?offset=1&limit=1').json()['items'], pages[1:2])
        for query in ['limit=201', 'limit=0', 'offset=-1']:
            self.assertEqual(self.client.get(f'/api/documents/{document_id}/chunks?{query}').status_code, 422)

    def test_mixed_and_no_text_documents(self) -> None:
        mixed_id = self.upload(text_pdf(['Readable', ''])).json()['id']
        blank_id = self.upload(sample_pdf()).json()['id']
        self.drain()
        mixed = self.metadata(mixed_id)['preparation']
        self.assertEqual(mixed['status'], 'ready_with_warnings')
        self.assertEqual(mixed['empty_pages'], [2])
        blank = self.metadata(blank_id)['preparation']
        self.assertEqual(blank['status'], 'no_text')
        self.assertEqual(blank['error'], 'No extractable text; OCR may be required')
        self.assertEqual(self.client.get(f'/api/documents/{blank_id}/chunks').json()['total'], 0)
        self.assertFalse(self.client.get(f'/api/documents/{blank_id}/pages').json()['items'][0]['has_text'])
        self.assertEqual(self.client.get(f'/api/documents/{blank_id}/content').status_code, 200)

    def test_failure_does_not_publish_and_retry(self) -> None:
        self.drain()
        document_id = self.upload(text_pdf(['Readable'])).json()['id']
        with patch('studymate.worker.split_chunks', side_effect=ValueError('private diagnostic')):
            self.assertTrue(process_next(self.worker))
        failed = self.metadata(document_id)['preparation']
        self.assertEqual(failed['status'], 'failed')
        self.assertNotIn('private diagnostic', failed['error'])
        self.assertEqual(self.worker.execute('SELECT count(*) AS n FROM document_pages WHERE document_id = %s',
            (UUID(document_id),)).fetchone()['n'], 0)
        self.assertFalse(process_next(self.worker))
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages').status_code, 409)
        self.assertEqual(self.client.post(f'/api/documents/{document_id}/prepare').status_code, 202)
        self.drain()
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'ready')

    def test_singleton_and_restart_recovery(self) -> None:
        with psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row) as second:
            self.assertFalse(acquire_lock(second))
        document_id = self.upload(sample_pdf()).json()['id']
        self.worker.execute("UPDATE document_preparations SET status = 'processing', attempt_id = %s, pages_processed = 1 WHERE document_id = %s",
            (uuid4(), UUID(document_id)))
        recover_interrupted(self.worker)
        self.assertEqual(self.metadata(document_id)['preparation']['pages_processed'], 0)
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'queued')
        self.drain()
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'no_text')

    def test_stale_attempt_cannot_publish(self) -> None:
        self.drain()
        document_id = self.upload(text_pdf(['Readable'])).json()['id']
        from studymate.preparation import split_chunks as original
        def invalidate(text):
            self.worker.execute('UPDATE document_preparations SET attempt_id = %s WHERE document_id = %s',
                (uuid4(), UUID(document_id)))
            return original(text)
        with patch('studymate.worker.split_chunks', side_effect=invalidate):
            process_next(self.worker)
        self.assertEqual(self.worker.execute('SELECT count(*) AS n FROM document_pages WHERE document_id = %s',
            (UUID(document_id),)).fetchone()['n'], 0)
        recover_interrupted(self.worker)
        self.drain()
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'ready')

    def test_deletion_during_processing_and_cascade(self) -> None:
        self.drain()
        document_id = self.upload(text_pdf(['Readable'])).json()['id']
        def remove(text):
            self.assertEqual(self.client.delete(f'/api/documents/{document_id}').status_code, 204)
            return []
        with patch('studymate.worker.split_chunks', side_effect=remove):
            process_next(self.worker)
        for suffix in ['pages', 'chunks']:
            self.assertEqual(self.client.get(f'/api/documents/{document_id}/{suffix}').status_code, 404)
        second_id = self.upload(text_pdf(['Readable'])).json()['id']
        self.drain()
        self.client.delete(f'/api/documents/{second_id}')
        for table in ['document_preparations', 'document_pages', 'document_chunks']:
            self.assertEqual(self.worker.execute(f'SELECT count(*) AS n FROM {table} WHERE document_id = %s',
                (UUID(second_id),)).fetchone()['n'], 0)

    def test_unknown_document(self) -> None:
        document_id = uuid4()
        self.assertEqual(self.client.post(f'/api/documents/{document_id}/prepare').status_code, 404)
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages').status_code, 404)
        self.assertEqual(self.client.get(f'/api/documents/{document_id}/chunks').status_code, 404)

    def test_upload_rolls_back_if_queue_insert_fails(self) -> None:
        @contextmanager
        def failing_connection():
            with connection() as conn:
                class QueueFailure:
                    def execute(self, query, parameters=()):
                        if query.startswith('INSERT INTO document_preparations'):
                            raise psycopg.IntegrityError('simulated queue failure')
                        return conn.execute(query, parameters)
                yield QueueFailure()
        name = f'atomic-{uuid4()}.pdf'
        with patch('studymate.documents.connection', failing_connection):
            self.assertEqual(self.upload(sample_pdf(), name).status_code, 503)
        self.assertEqual(self.worker.execute('SELECT count(*) AS n FROM documents WHERE filename = %s',
            (name,)).fetchone()['n'], 0)

    def test_results_stay_private_during_chunking(self) -> None:
        self.drain()
        document_id = self.upload(text_pdf(['First page', 'Second page'])).json()['id']
        def inspect(text):
            preparation = self.metadata(document_id)['preparation']
            self.assertEqual(preparation['phase'], 'chunking')
            self.assertEqual(preparation['pages_processed'], 2)
            self.assertEqual(self.client.get(f'/api/documents/{document_id}/pages').status_code, 409)
            self.assertEqual(self.worker.execute('SELECT count(*) AS n FROM document_pages WHERE document_id = %s',
                (UUID(document_id),)).fetchone()['n'], 0)
            return split_chunks(text)
        with patch('studymate.worker.split_chunks', side_effect=inspect):
            process_next(self.worker)
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'ready')

    def test_connection_loss_aborts_processing(self) -> None:
        self.drain()
        document_id = self.upload(text_pdf(['First page'])).json()['id']
        with patch('studymate.worker.normalize_text', side_effect=psycopg.OperationalError('lock session lost')):
            with self.assertRaises(psycopg.OperationalError):
                process_next(self.worker)
        self.assertEqual(self.metadata(document_id)['preparation']['status'], 'processing')
        recover_interrupted(self.worker)

    def test_migration_queues_existing_documents_and_is_repeatable(self) -> None:
        # An isolated schema exercises the v1 -> v2 upgrade without resetting test data.
        schema = 'migration_' + uuid4().hex
        with psycopg.connect(self.database_url, autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            url = psycopg.conninfo.make_conninfo(self.database_url, options=f'-c search_path={schema}')
            document_id = uuid4()
            content = sample_pdf()
            with psycopg.connect(url) as conn:
                for statement in MIGRATIONS[0][1]:
                    conn.execute(statement)
                conn.execute('CREATE TABLE schema_migrations (version integer PRIMARY KEY)')
                conn.execute('INSERT INTO schema_migrations VALUES (1)')
                conn.execute("""INSERT INTO documents (id, filename, size_bytes, page_count, sha256, content)
                    VALUES (%s, 'existing.pdf', %s, 1, %s, %s)""", (document_id, len(content), '0' * 64, content))
            migrate(url)
            migrate(url)
            with psycopg.connect(url) as conn:
                self.assertEqual(conn.execute('SELECT document_id, status FROM document_preparations').fetchall(),
                    [(document_id, 'queued')])
                self.assertEqual(conn.execute('SELECT content FROM documents').fetchone()[0], content)
        finally:
            with psycopg.connect(self.database_url, autocommit=True) as conn:
                conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
