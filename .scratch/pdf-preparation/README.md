# Approved PDF preparation tickets

Six approved vertical slices are saved as local Markdown tickets in the issues directory. No GitHub publication is required.

| Ticket | Title | Blocked by |
| --- | --- | --- |
| 01 | Inspect prepared text by physical page | None |
| 02 | Reprocess documents while retaining published results | 1 |
| 03 | Inspect layout-aware text and page-image fallbacks | 1 |
| 04 | Inspect structured tables and prepare row-aware chunks | 3 |
| 05 | Inspect equations with linked visual evidence | 3 |
| 06 | Inspect diagrams with source captions and fallbacks | 3 |

All six tickets are resolved, with checked acceptance criteria and explicit blocking edges retained for context. The implementation and validation are recorded in review.md.

The spec is saved as spec.md beside these tickets. The drafts directory retains the earlier issue-body drafts for reference; the issues directory is the authoritative ticket set.

Specification: the repository's issue-ready PDF preparation specification. Testing approach: the user confirmed API integration tests with a real test database and deterministic PDFs exercising the real worker, supplemented by visual inspection.
