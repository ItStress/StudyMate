# Inspectable PDF preparation

Status: implemented through the six approved local tickets. The issue-ready specification and completed tickets record the final scope and verification.

The preparation pipeline and diagnostic APIs remain in use. The RAG implementation removes the frontend inspector and reprocessing controls, keeps the complete original PDF preview, and adds separate local embedding/indexing. The inspector section below describes the earlier UI. See the root README for current behavior.

## Purpose and scope

Prepare English PDFs with selectable text for later question answering, explanations, and summaries with document and physical-page citations. This change improves extraction and provides an in-app inspector. It does not implement embeddings, retrieval, or chat.

All processing runs locally without AI models or OCR. Structured results are best-effort evidence, not a guarantee that mathematical or visual meaning has been recovered.

## Extraction results

- Preserve original PDFs and canonical one-based physical page references.
- Extract text in geometric reading order, including multicolumn layouts. Flag detected ambiguity rather than claiming every layout is correct.
- Exclude detected repeated headers and footers from retrieval-oriented text while retaining them as inspectable source evidence.
- Extract tables as rows and cells with page and region references. Keep portions on different pages separate; do not infer cross-page table merges.
- Preserve extractable equation text and rendered region crops for verification. No guaranteed LaTeX conversion or mathematical interpretation. Flag identifiable extraction problems; some mistakes may remain undetected.
- Preserve diagram crops and associate existing captions when identifiable. Do not generate captions or interpret diagram relationships. Rendered crops must retain vector drawings as well as bitmap images.
- Use a full-page image fallback and a warning where reliable region boundaries or caption association cannot be established.
- Preserve useful partial results with page- or element-specific warnings. Completely unsuccessful processing must not publish apparently usable content.

## Prepared chunks

Generate chunks from the improved content in reading order, with original document and physical-page provenance. Keep table and equation content together where possible. Split oversized tables at row boundaries and repeat available headers. Link equation text to its crop and diagram caption text to its visual evidence. Images themselves are not treated as interpreted text.

Keep page-local provenance in this version. Chunk-size parameters and extraction heuristics are implementation settings, not domain terminology or claims of retrieval quality.

## Inspector

Provide a page-by-page in-app view alongside the original PDF. Show extracted text, structured tables, equation crops and text, diagram crops and available captions, fallback page images, and warnings. Show the published extraction version and whether it is an older result during reprocessing.

Downloads and manual content editing are outside this version.

## Reprocessing

Provide an explicit Reprocess action for completed documents; pipeline upgrades do not automatically rerun them. Keep the last published results accessible while a new attempt is queued or running and if that attempt fails. Replace published results atomically only after the new attempt produces usable results. Usable partial results may replace prior results with their warnings visible.

Separate published-result metadata from current-attempt state so the inspector can display the correct version and still report progress or failure. Preserve existing deletion and stale-attempt protections for all new artifacts.

## Implementation direction

Evaluate pdfplumber for deterministic text geometry and tables, with its PDFium-backed rendering for page and region images. Retain existing pypdf upload validation and the local sequential worker. These are implementation recommendations, subject to verification against installed versions and extraction fixtures.

Extend the existing PostgreSQL artifact storage with typed content, region provenance, warnings, and rendered assets. Process/render pages with bounded resources instead of accumulating all image data in memory. Do not introduce an external service or model runtime.

Official capability references:

- [pdfplumber extraction, tables, crops, and rendering](https://github.com/jsvine/pdfplumber)
- [pdfplumber MIT license](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt)
- [pypdfium2 licensing and runtime limitations](https://github.com/pypdfium2-team/pypdfium2)

## Verification

Use deterministic PDF fixtures covering ordinary text, multiple columns, repeated margins, tables with and without drawn borders, equations, bitmap images, vector diagrams, captions, ambiguous content, and tables spanning pages. Assert provenance, structured content, warnings, and meaningful chunk boundaries; visually inspect rendered crops and the inspector.

Verify partial publication, failed reprocessing with previous results still accessible, successful atomic replacement, deletion, and stale-worker behavior against a separate PostgreSQL test database. Run the required backend tests and endpoint checks, and frontend lint and build.

No representative study PDFs were found in the repository. Synthetic fixtures can verify behavior, but extraction quality on the user's actual material remains unverified until representative PDFs are available.
