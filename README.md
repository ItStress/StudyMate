# StudyMate

StudyMate is a web app for asking questions about your own study materials. Its goal is to turn uploaded PDFs and notes into answers that cite the source document, page, and supporting passage, so every answer can be checked against the original material.

The project is at an early stage. The repository currently contains a React frontend scaffold and a FastAPI backend with a health endpoint. Document upload, retrieval, chat, and local AI inference are planned features, not yet implemented.

## Planned features

- Upload, list, organize, and delete PDF documents.
- Extract text while preserving the source page number. Add OCR for scanned PDFs.
- Show document processing progress and errors.
- Ask questions about one or more selected documents.
- Return answers with clickable citations and relevant source passages.
- Say when the selected documents do not provide enough evidence.
- Save conversation history and provide a demo with sample documents.

## Intended approach

StudyMate will use retrieval-augmented generation (RAG). During ingestion, the backend will extract text from each page, split it into passages, and store each passage with its document and page number. At question time, it will retrieve passages from the selected documents and provide them to a locally hosted language model. The backend will return the answer together with references to the passages used.

The intended stack uses open-source components: React, TypeScript, and Vite for the frontend; Python and FastAPI for the backend; PostgreSQL with pgvector for storage and retrieval; and locally run embedding and language models. These RAG components are not installed or connected yet.

## Repository layout

```text
StudyMate/
├── backend/    FastAPI application and Python project configuration
└── frontend/   React, TypeScript, and Vite application
```

## Run locally

You will need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and a Node.js installation compatible with the Vite version in `frontend/package.json`.

Start the backend in one terminal:

```sh
cd backend
uv sync
uv run studymate
```

The API listens on `http://127.0.0.1:8000`. Check `http://127.0.0.1:8000/health` for `{"status":"ok"}`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Start the frontend in another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`. The frontend currently displays a placeholder and does not call the backend yet.

## Current checks

```sh
cd frontend
npm run lint
npm run build
```

The backend health endpoint can be checked at `/health` while the server is running.
