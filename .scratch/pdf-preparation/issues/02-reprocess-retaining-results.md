# 02: Reprocess documents while retaining published results

**What to build:** Explicitly reprocess completed documents while keeping their previous published results available. Show new-attempt progress or failure separately, identify older displayed results, and atomically replace them only when the new attempt produces usable output.

**Blocked by:** 01: Inspect prepared text by physical page.

**Status:** resolved

- [x] The document UI exposes an explicit Reprocess action for completed documents; existing failed-attempt retry remains available.
- [x] Pipeline changes do not automatically rerun documents, and overlapping preparation attempts for one document are prevented.
- [x] Previously published content and extraction-version metadata remain accessible while a new attempt is queued or processing.
- [x] The inspector identifies displayed results as older and separately reports the new attempt's progress or failure.
- [x] A failed or completely unsuccessful rerun retains the previous usable results; a first preparation without usable text is not misrepresented as successful retrieval-ready preparation.
- [x] A usable new result replaces all published artifacts and their version atomically; useful partial results may replace old results with visible warnings.
- [x] Deleting a document during reprocessing prevents stale attempts from restoring content; worker restart recovery remains correct.
- [x] API integration tests exercise old-result visibility, duplicate attempts, failure preservation, successful replacement, partial publication, restart recovery, and deletion; visually verify the UI and run required backend/frontend checks.

## Scope

English PDFs with selectable text; local preparation without AI models. No OCR, embeddings, retrieval, chat, downloads, manual corrections, or automatic pipeline-upgrade reprocessing.

## Answer

Implemented and verified. The complete backend suite (38 tests), frontend lint/build, applicable visual checks, and both review axes passed. See ../review.md for evidence and limitations.
