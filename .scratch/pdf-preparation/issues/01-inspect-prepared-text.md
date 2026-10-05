# 01: Inspect prepared text by physical page

**What to build:** Navigate prepared text and existing warnings page by page beside the original PDF, with canonical physical-page references and the published extraction version. Establish published-result metadata without changing extraction behavior.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The document inspector allows selecting any physical page and displays its extracted text beside access to the same page in the original PDF; physical pages use one-based PDF positions.
- [x] Blank or textless pages remain navigable and their existing warnings are shown rather than omitted.
- [x] The published extraction version and page/document provenance are visible through the API and inspector.
- [x] Existing completed documents remain inspectable after the compatible persistence change; pending first preparations clearly show that no published result exists.
- [x] The API serves coherent published page results, with valid pagination and page selection boundaries.
- [x] Published-result metadata is separate enough from attempt state to support subsequent reprocessing without conflating displayed results with current progress.
- [x] Existing upload validation, preparation, original-PDF access, deletion, restart recovery, and stale-attempt behavior remain functional.
- [x] API integration tests use deterministic PDFs and the real worker against a separate PostgreSQL test database; visually verify page navigation, and run backend endpoint checks plus frontend lint/build.

## Scope

English PDFs with selectable text; local preparation without AI models. No OCR, embeddings, retrieval, chat, downloads, manual corrections, or automatic pipeline-upgrade reprocessing.

## Answer

Implemented and verified. The complete backend suite (38 tests), frontend lint/build, applicable visual checks, and both review axes passed. See ../review.md for evidence and limitations.
