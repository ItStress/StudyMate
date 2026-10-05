# 06: Inspect diagrams with source captions and fallbacks

**What to build:** Inspect diagram crops with existing source captions where identifiable, preserving bitmap and vector graphics. Link caption text to diagram evidence for future use, with warned full-page fallbacks where region or caption association is uncertain.

**Blocked by:** 03: Inspect layout-aware text and page-image fallbacks.

**Status:** resolved

- [x] Deterministic bitmap and vector diagram fixtures produce inspectable rendered crops with document, physical-page, and region provenance.
- [x] Existing captions are associated using deterministic source-layout rules; the pipeline neither generates descriptions nor interprets diagram relationships.
- [x] Uncertain diagram boundaries or caption association retain full-page visual evidence and an attributed warning.
- [x] Caption text contributes to prepared chunks in reading order and links to the diagram evidence without duplicate or invented caption content.
- [x] Visual assets remain evidence rather than being presented as interpreted textual descriptions.
- [x] Useful surrounding content remains available when diagram recovery is partial; warnings are visible for the affected page or element.
- [x] Diagram assets, captions, and chunk links remain coherent through reprocessing, publication, deletion, and stale-attempt rejection.
- [x] API integration fixtures verify bitmap/vector evidence, caption links, uncertain association, and fallback behavior; visually compare crops and captions and run required backend/frontend checks.

## Scope

English PDFs with selectable text; local preparation without AI models. No OCR, embeddings, retrieval, chat, downloads, manual corrections, or automatic pipeline-upgrade reprocessing.

## Answer

Implemented and verified. The complete backend suite (38 tests), frontend lint/build, applicable visual checks, and both review axes passed. See ../review.md for evidence and limitations.
