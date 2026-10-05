# StudyMate

StudyMate is a web app for asking questions about your own study materials. Its goal is to turn uploaded PDFs and notes into answers that cite the source document, page, and supporting passage, so every answer can be checked against the original material.

The project is at an early stage. The React frontend uploads PDFs through FastAPI, lists and previews saved documents, and removes them from PostgreSQL. FastAPI can also answer general questions through a locally running Ollama model. PDF retrieval and the chat frontend are planned features.

## Planned features

- Organize PDF documents into collections.
- Extract text while preserving the source page number. Add OCR for scanned PDFs.
- Show document processing progress and errors.
- Ask questions about one or more selected documents.
- Return answers with clickable citations and relevant source passages.
- Say when the selected documents do not provide enough evidence.
- Save conversation history and provide a demo with sample documents.

## Intended approach

StudyMate will use retrieval-augmented generation (RAG). During ingestion, the backend will extract text from each page, split it into passages, and store each passage with its document and page number. At question time, it will retrieve passages from the selected documents and provide them to a locally hosted language model. The backend will return the answer together with references to the passages used.

The stack uses React, TypeScript, Vite, and Tailwind CSS for the frontend; Python and FastAPI for the backend; and PostgreSQL for PDF storage. pgvector, text extraction, and locally run embedding and language models are planned for retrieval.

## Repository layout

```text
StudyMate/
├── backend/    FastAPI application and Python project configuration
└── frontend/   React, TypeScript, and Vite application
```

## Run locally

You will need Docker, Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and a Node.js installation compatible with the Vite version in `frontend/package.json`.

Start PostgreSQL from the repository root:

```sh
docker compose up -d --wait postgres
```

Docker stores data in a named volume and exposes PostgreSQL only on `127.0.0.1:15432` by default, leaving the usual `5432` host port free for another PostgreSQL instance. Set `STUDYMATE_POSTGRES_PORT` before `docker compose up` if `15432` is also occupied, then use the same port in the connection URLs below. For local development, the default password is `studymate-local`; set `POSTGRES_PASSWORD` before the first `docker compose up` to choose another password. Existing volumes retain the password chosen when they were created.

Start the backend in one terminal:

```sh
cd backend
uv sync
```

Set `DATABASE_URL` in that shell, using `backend/.env.example` as a reference. On PowerShell, run:

```powershell
$env:DATABASE_URL = 'postgresql://studymate:studymate-local@127.0.0.1:15432/studymate'
uv run studymate-migrate
uv run studymate
```

On a POSIX shell, use `export DATABASE_URL=postgresql://studymate:studymate-local@127.0.0.1:15432/studymate` before the same two `uv run` commands. Match the URL port to `STUDYMATE_POSTGRES_PORT` and the password to Docker's `POSTGRES_PASSWORD`. Do not commit real database passwords. Re-run `uv run studymate-migrate` after future schema changes.

If `uv run studymate-migrate` fails with `ModuleNotFoundError: No module named 'studymate'` on macOS, the editable install may be hidden from Python. Run `uv run --no-editable studymate-migrate` and `uv run --no-editable studymate` instead. This installs a copy of the backend package in the virtual environment, so run `uv sync --no-editable --reinstall-package studymate` after changing backend source files.

The API listens on `http://127.0.0.1:8000`. Check `http://127.0.0.1:8000/health` for `{"status":"ok"}`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Start the frontend in another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`. Vite proxies `/api` to the local FastAPI server. In a deployed setup, route `/api` to FastAPI on the same origin as the frontend.

The API provides `POST /api/documents` (multipart field `file`), `GET /api/documents`, `GET /api/documents/{id}/content`, and `DELETE /api/documents/{id}`. Each PDF must be at most 25 MiB. The browser checks type, size, and PDF signature for quick feedback; FastAPI repeats validation, rejects encrypted or malformed PDFs, and stores the original bytes with metadata. This first version is for trusted local single-user use and has no authentication.

## Local language model

Install and start [Ollama](https://ollama.com/download) on the same computer as the backend, then run `ollama pull qwen3:4b`. StudyMate uses `qwen3:4b` by default. To use another downloaded model, set `OLLAMA_CHAT_MODEL` to its name in the backend shell. The default Ollama URL is `http://127.0.0.1:11434`; set `OLLAMA_BASE_URL` if yours differs. `backend/.env.example` lists these variables. The backend reads shell environment variables; it does not load the example file automatically.

Start the API with `cd backend && uv run studymate`. Open `/docs` and call `POST /api/chat` with `{"question":"Explain gravity simply"}`. The response is `{"answer":"..."}`. The endpoint currently answers general questions only; it does not read uploaded PDFs or provide citations. Ollama errors are reported as `502`, connection errors or an empty model setting as `503`, and timeouts as `504`.

The chat request disables the model's thinking mode for faster answers and allows up to three minutes for Ollama to respond. The first answer can take longer while Ollama loads the model. If `/api/chat` still times out, try the same question directly with `ollama run qwen3:4b` to check whether the model runs on your computer.

## Current checks

```sh
cd frontend
npm run lint
npm run build
```

The backend health endpoint can be checked at `/health` while the server is running.

The PostgreSQL container also creates a separate `studymate_test` database on a fresh volume. To run backend integration tests, set `TEST_DATABASE_URL` to `postgresql://studymate:studymate-local@127.0.0.1:15432/studymate_test`, then run `uv run python -m unittest discover -s tests` from `backend/`. Tests require the separate database and do not touch the app database.
