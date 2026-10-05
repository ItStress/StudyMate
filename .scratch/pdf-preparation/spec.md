# Inspectable, model-free PDF preparation

## Problem Statement

StudyMate users need inspectable preparation of study documents before using them for question answering, explanations, and summaries with page citations. Existing preparation produces plain text and page-linked chunks, but can lose table structure, equation notation, diagrams, and multicolumn reading order. Repeated headers and footers can pollute future retrieval. Users cannot currently inspect extracted results or reprocess completed documents.

Users need to compare preparation results with the original, identify incomplete evidence, and retain accurate physical-page references. Processing must run locally without AI models.

## Solution

Improve preparation of English PDFs with selectable text and provide a page-by-page inspector beside the original PDF. Preserve ordered text, structured tables, equation text with visual crops, and diagrams with existing captions where identifiable. Keep useful partial content with warnings and full-page image fallbacks where recovery is uncertain.

Generate chunks from the improved content. Allow explicit reprocessing while retaining the last published results until a new usable result replaces them. This feature prepares evidence for later RAG; it does not implement retrieval or answering.

## User Stories

1. As a learner, I want to prepare English PDFs with selectable text, so that my study material is available for later retrieval.
2. As a learner, I want preparation to run locally, so that document contents are not sent to external processing services.
3. As a learner, I want preparation without AI models, so that this stage does not depend on model downloads or a model runtime.
4. As a learner, I want the original document preserved, so that I can verify extracted evidence.
5. As a learner, I want every extracted element linked to its physical page, so that future citations identify the correct source.
6. As a learner, I want canonical page references to use one-based PDF positions, so that printed labels cannot misdirect citations.
7. As a learner, I want text in reading order, so that its meaning is retained.
8. As a learner, I want multicolumn content ordered sensibly, so that unrelated columns are not interleaved.
9. As a learner, I want detected layout ambiguity flagged, so that I can inspect potentially misleading results.
10. As a learner, I want repeated headers and footers excluded from retrieval-oriented content, so that page furniture does not dominate later searches.
11. As a learner, I want excluded content retained as inspectable evidence, so that mistaken exclusions can be recognized.
12. As a learner, I want tables represented as rows and cells, so that relationships between values survive preparation.
13. As a learner, I want tables linked to page regions, so that I can verify their origin.
14. As a learner, I want tables spanning pages preserved as separate portions, so that preparation does not infer incorrect joins.
15. As a learner, I want available equation text preserved, so that recoverable symbols remain usable.
16. As a learner, I want equation crops beside their text, so that I can verify mathematical arrangement visually.
17. As a learner, I want identifiable equation extraction problems flagged, so that incomplete text is not presented as assured mathematical meaning.
18. As a learner, I want diagram crops preserved, so that their visual evidence remains available.
19. As a learner, I want vector drawings preserved alongside bitmap images, so that PDF drawing format does not determine whether evidence survives.
20. As a learner, I want existing captions linked to diagrams when identifiable, so that source text accompanies visual evidence.
21. As a learner, I want warned full-page image fallbacks for uncertain crop boundaries or caption matching, so that uncertain extraction does not discard evidence.
22. As a learner, I want useful partial results retained, so that one difficult element does not make the whole document unusable.
23. As a learner, I want warnings associated with affected pages or elements, so that I know what to inspect.
24. As a learner, I want page-by-page inspection beside the original PDF, so that comparison is straightforward.
25. As a learner, I want the inspector to show text, tables, equation evidence, diagram evidence, and fallbacks, so that I can review the preparation result.
26. As a learner, I want the published extraction version visible, so that I know which preparation produced the results.
27. As a learner, I want chunks built from improved content in reading order, so that later retrieval uses the evidence I inspected.
28. As a learner, I want tables and equations kept together where possible, so that chunk boundaries preserve context.
29. As a learner, I want oversized tables split by rows with available headers repeated, so that table fragments remain understandable.
30. As a learner, I want equation chunks linked to crops and caption text linked to diagram evidence, so that future consumers can access supporting appearances.
31. As a learner, I want explicit reprocessing of completed documents, so that I can regenerate results after pipeline improvements.
32. As a learner, I want pipeline changes to avoid automatic reprocessing, so that inspected results do not change unexpectedly.
33. As a learner, I want previous results accessible while reprocessing runs, so that usable evidence remains available.
34. As a learner, I want previous results retained after failed reprocessing, so that a failed attempt does not remove useful work.
35. As a learner, I want rerun progress and failure shown separately from published results, so that I understand both states.
36. As a learner, I want older results clearly identified during reprocessing, so that I do not confuse them with new results.
37. As a learner, I want new results published together, so that I never see a mixture of old and new extraction artifacts.
38. As a learner, I want deletion to remove all prepared artifacts and prevent stale processing from restoring them, so that deleted documents remain deleted.

## Implementation Decisions

- Extend the existing document preparation worker, persistence, document API, and document preview feature. Retain existing upload validation, original PDF storage, the sequential local worker, progress reporting, restart recovery, and stale-attempt protections.
- Process locally without AI models or OCR. Preparation does not include embeddings, retrieval, or answering.
- Evaluate pdfplumber for deterministic text geometry and table extraction, with PDFium-backed rendering for crops and page images. This is an implementation recommendation, not a user-selected dependency; verify installed versions and fixture behavior before adoption.
- Extend existing PostgreSQL artifact storage for typed content, table rows and cells, visual assets, region provenance, warnings, and published-result metadata. Bound rendering resources instead of accumulating an entire document's images in memory.
- Use one-based physical-page positions as canonical references. Preserve region provenance for extracted elements and visual assets.
- Derive reading order from geometry, including columns and spanning content. Flag detectable ambiguity; do not promise correct interpretation of arbitrary layouts.
- Detect repeated margin text across pages. Exclude it from retrieval-oriented content while retaining original evidence and exclusion information.
- Preserve table rows and cells with page and region references. Keep portions on different pages separate rather than automatically merging them.
- Preserve extractable equation text with rendered crops. Do not promise faithful LaTeX conversion or mathematical interpretation. Flag identifiable problems; some mistakes may remain unrecognized.
- Preserve diagram regions by rendering both bitmap and vector content. Associate existing captions using deterministic layout rules; do not generate descriptions or infer diagram meaning.
- Provide a warned full-page image fallback when reliable region boundaries or caption association cannot be established.
- Publish useful partial results with warnings. A completely unsuccessful attempt must not replace an existing usable result or appear to be successful preparation.
- Generate chunks from improved content in reading order, with physical-page provenance and links to supporting elements. Keep equations together where possible; split oversized tables by rows and repeat available headers. Diagram captions supply text; images are not interpreted as textual descriptions.
- Evolve the current plain-text chunk contract where necessary. Repeating table headers means a chunk cannot always be one contiguous substring of page text; maintain truthful provenance rather than inventing offsets.
- Extend document API contracts to expose structured page content, warnings, rendered assets, and their relationships to chunks. Serve artifacts from a coherent published result.
- Separate current-attempt state from published-result metadata and version. Keep published artifacts available while a new attempt is queued, processing, or failed.
- Extend preparation requests to completed documents. Reprocessing is explicit, pipeline upgrades do not automatically rerun documents, and overlapping attempts for one document must be prevented. Preserve failed-attempt retry behavior.
- Atomically replace published artifacts only after a new usable result finishes. Usable partial results can replace older results, with their warnings visible.
- Add page navigation and an inspector beside the original PDF. Show extracted text, tables, equation crops and text, diagram crops and captions, fallback images, warnings, published version, older-result identification, and rerun progress or failure.
- Keep page composition focused on composition and group inspection behavior with the document feature. Use English user-facing text and the existing frontend styling conventions.
- Extend deletion and stale-attempt protections to every new artifact and rendered asset.

## Testing Decisions

- The user confirmed the main testing seam: existing document API integration tests with a real test database and deterministic PDFs, exercising the real worker. Supplement these with visual checks of crops and the inspector.
- Prefer the highest existing seam: upload a PDF, process it, and inspect public API results. Test external behavior rather than extractor calls, private helpers, or database schema details. Avoid introducing several new test seams.
- Existing preparation API tests provide prior art for upload-to-publication behavior, page references, pagination, warnings, retry, restart recovery, atomicity, stale attempts, and deletion. Extend these scenarios.
- Cover ordinary text, multicolumn order, repeated-margin exclusions, ruled and unruled tables, equation evidence, bitmap and vector diagrams, captions, ambiguous content, blank pages, and tables spanning pages.
- Assert structured relationships, recoverable symbols, physical-page and region provenance, warning attribution, meaningful chunk boundaries, repeated table headers, and links to visual evidence. Avoid brittle assertions on arbitrary image bytes or internal heuristic steps.
- Verify useful partial publication, first attempts without recoverable text, old results accessible during reprocessing and after failure, successful atomic replacement, and separate attempt progress and published-version metadata.
- Verify deletion of new artifacts, stale-attempt rejection, restart recovery, and duplicate-attempt protection.
- Visually compare crop contents, full-page fallbacks, and the page-by-page inspector with source PDFs. Text assertions alone cannot verify equation layout or vector drawing preservation.
- Run backend unittest discovery against a separate PostgreSQL test database, verify health and changed endpoints, and run frontend lint and build. No implementation tests have been run for this specification-only change.
- Synthetic fixtures establish repeatable behavior but do not prove quality on arbitrary study PDFs. Assess representative user documents when available before claiming quality for the user's corpus.

## Out of Scope

AI models and model downloads; OCR and scanned-document text recognition; non-English extraction requirements; embeddings, vector indexing, retrieval, chat, answer generation, explanations, and summaries; guaranteed LaTeX reconstruction or mathematical interpretation; diagram semantics and generated captions; automatic cross-page table merging; printed page labels as canonical citation identifiers; downloads; manual correction of extracted content; automatic reprocessing after pipeline upgrades; guaranteed detection of every extraction mistake.

## Further Notes

- This specification synthesizes the completed design interview and confirmed testing approach. The user subsequently invoked implementation of the six approved local tickets. All six are implemented and verified; the completed ticket set records acceptance and the review report records validation.
- Use the project glossary's Document, Citation, Physical page, Table, Equation, Diagram, Preparation, and Reprocessing vocabulary. The accepted ADR records the model-free evidence-preservation scope and its trade-off against semantic recovery.
- No representative study PDFs were found in the repository. Existing tests use generated PDFs; real-document extraction quality remains unverified.
- The scope accepts best-effort recovery with visual evidence and warnings. A visual-only page can remain inspectable without providing text for future retrieval.
- Official capability references: [pdfplumber documentation](https://github.com/jsvine/pdfplumber), [pdfplumber license](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt), and [pypdfium2 licensing and limitations](https://github.com/pypdfium2-team/pypdfium2).
- The user chose local Markdown tickets without GitHub publication. The approved six-ticket breakdown is saved under the local PDF preparation issue directory with explicit blocking edges and `ready-for-agent` status. The project-wide triage-label mapping remains proposed pending the user's choice.
