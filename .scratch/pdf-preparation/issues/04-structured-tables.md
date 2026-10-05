# 04: Inspect structured tables and prepare row-aware chunks

**What to build:** Inspect extracted tables as rows and cells beside the source PDF. Preserve page-local portions and produce table-aware chunks that split oversized tables by rows and repeat available headers.

**Blocked by:** 03: Inspect layout-aware text and page-image fallbacks.

**Status:** resolved

- [x] Deterministic ruled and unruled table fixtures expose structured rows and cells through the document API and inspector.
- [x] Each table portion retains its document, physical page, and source region, with visual comparison available.
- [x] A table continuing on another physical page remains a separate portion; preparation does not infer cross-page joins.
- [x] Identified uncertain table recovery produces attributed warnings while retaining useful surrounding text and visual evidence.
- [x] Table serialization appears in the improved reading order without unintended duplicate extraction of the same table text into prose chunks.
- [x] Chunks keep table content together where possible; oversized tables split by rows and repeat available headers, with truthful provenance rather than invented contiguous text offsets.
- [x] Published table records and chunk links remain coherent through reprocessing, atomic publication, deletion, and stale-attempt rejection.
- [x] API integration fixtures verify cell relationships, page-local portions, header repetition, and chunk boundaries; visually inspect tables and run required backend/frontend checks.

## Scope

English PDFs with selectable text; local preparation without AI models. No OCR, embeddings, retrieval, chat, downloads, manual corrections, or automatic pipeline-upgrade reprocessing.

## Answer

Implemented and verified. The complete backend suite (38 tests), frontend lint/build, applicable visual checks, and both review axes passed. See ../review.md for evidence and limitations.
