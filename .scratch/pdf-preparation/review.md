# PDF preparation implementation review

Starting commit: `3ff3259bc39be64ea75351d8e940f27d1a024bc6`. Reviewed the staged implementation and its existing uncommitted preparation prerequisites against the six approved tickets and repository guidelines.

## Standards

Final review: 0 hard violations and 0 remaining substantive smell findings. The initial content-shape finding was resolved using shared discriminated evidence models, validated extraction output, typed API contracts, and page objects retained until publication.

## Spec

Final review: 0 unresolved actionable findings. The four initial findings were fixed: equation crops now retain nearby raised/stacked glyphs; unsuccessful visual-only reruns retain previous evidence; chunk references intersect actual supporting spans; adjacent prose forms normal passages around structured elements.

## Verification

- All 38 backend unit/integration tests passed against a separate PostgreSQL test database through the required unittest discovery command.
- Frontend ESLint and TypeScript/Vite production build passed.
- Health and changed page endpoints were checked against the running local API.
- A completed v1 preparation was migrated in an isolated test schema and remained inspectable through the public page/chunk APIs.
- Visual verification covered the rendered original beside structured content, table cells, equation and bitmap/vector diagram crops, captions, physical-page navigation including a blank page, and old-result visibility while reprocessing was queued. Successful replacement was also verified.
- Review regressions cover superscripts, stacked fractions, row-aware chunks with repeated headers, unruled numeric tables, truthful text-chunk references, coherent prose passages, stale publication requests, and retained text/visual evidence after failures.

The visual demo uses a separate preview database; no application documents were used. Docker's engine was unavailable, so tests used the installed local PostgreSQL server in an isolated cluster. No AI models or document-processing services were used. Real-document quality remains unverified until representative study PDFs are available.
