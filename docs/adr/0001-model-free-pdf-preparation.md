---
status: accepted
---

# Preserve evidence during model-free PDF preparation

StudyMate's initial preparation pipeline runs locally without AI models and prepares English PDFs with selectable text for later RAG. Rather than inferring mathematical notation or diagram meaning, it preserves extractable text, table structure, and page-linked visual evidence, with warnings and page-image fallbacks where recovery is uncertain. This scope trades semantic recovery for a model-free pipeline whose output users can inspect; future retrieval must not assume that every visual element has a faithful textual representation.
