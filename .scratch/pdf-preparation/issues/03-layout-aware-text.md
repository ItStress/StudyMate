# 03: Inspect layout-aware text and page-image fallbacks

**What to build:** Inspect locally extracted text in geometric reading order, including multicolumn pages, with repeated headers and footers excluded from retrieval-oriented content but retained for inspection. Expose layout warnings and full-page visual fallbacks, and generate text chunks from the improved ordered content.

**Blocked by:** 01: Inspect prepared text by physical page.

**Status:** resolved

- [x] Preparation uses local deterministic PDF extraction and rendering without AI models, OCR, external document-processing services, or model downloads.
- [x] Representative deterministic single-column and multicolumn fixtures yield meaningful text reading order with physical-page and region provenance.
- [x] Repeated margin content is excluded from retrieval-oriented text and chunks while its source evidence and exclusion information remain inspectable.
- [x] Identified layout ambiguity or unsupported evidence produces page- or element-specific warnings; the UI does not claim universal extraction correctness.
- [x] Full-page rendered images are available in the inspector where region recovery is uncertain, with local asset access tied to a coherent publication.
- [x] Text chunks derive from the improved reading order and retain correct physical-page references and provenance.
- [x] Rendering and publication use bounded resources; bitmap and vector appearances survive in page images, with shared region-rendering capability available to later slices.
- [x] Partial usable content stays available with warnings; deletion and stale-attempt protections cover new content and image artifacts.
- [x] API integration fixtures cover columns, spanning text, repeated margins, ambiguous layouts, and empty pages; visually inspect fallbacks and exclusions and run required backend/frontend checks.

## Scope

English PDFs with selectable text; local preparation without AI models. No OCR, embeddings, retrieval, chat, downloads, manual corrections, or automatic pipeline-upgrade reprocessing.

## Answer

Implemented and verified. The complete backend suite (38 tests), frontend lint/build, applicable visual checks, and both review axes passed. See ../review.md for evidence and limitations.
