# 05: Inspect equations with linked visual evidence

**What to build:** Compare extractable equation text with its rendered crop in the page-by-page inspector. Preserve available symbols and arrangement evidence, flag identifiable recovery problems, and link prepared chunks to equation crops.

**Blocked by:** 03: Inspect layout-aware text and page-image fallbacks.

**Status:** resolved

- [x] Recoverable equation candidates expose available text, physical-page and region provenance, and rendered crops through the API and inspector.
- [x] Rendered crops preserve visible notation and arrangement for visual verification, including available superscript/subscript or fraction appearances.
- [x] Detection and recovery are deterministic and local; no AI model, OCR, guaranteed LaTeX conversion, or inferred mathematical interpretation is introduced.
- [x] Identifiable incomplete recovery is flagged, and the UI does not imply that all malformed equations will be detected.
- [x] Uncertain region boundaries retain full-page fallback evidence with a warning rather than discarding the source appearance.
- [x] Equation text stays together in chunks where possible and links to its visual evidence without falsely claiming intact mathematical meaning.
- [x] Equation artifacts and chunk links remain coherent through publication, reprocessing, deletion, and stale-attempt rejection.
- [x] API integration fixtures verify recoverable symbols, provenance, warnings, and crop links; visually compare equation notation and crop bounds and run required backend/frontend checks.

## Scope

English PDFs with selectable text; local preparation without AI models. No OCR, embeddings, retrieval, chat, downloads, manual corrections, or automatic pipeline-upgrade reprocessing.

## Answer

Implemented and verified. The complete backend suite (38 tests), frontend lint/build, applicable visual checks, and both review axes passed. See ../review.md for evidence and limitations.
