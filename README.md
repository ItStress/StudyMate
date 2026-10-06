# StudyMate

StudyMate is a web app for asking questions about your own study materials. Its goal is to turn uploaded PDFs and notes into answers that cite the source document, page, and supporting passage, so every answer can be checked against the original material.

The project is at an early stage. The React frontend uploads PDFs through FastAPI, lists and previews saved documents, and removes them from PostgreSQL. A local worker prepares page text and passages for future retrieval. Retrieval, embeddings, chat, and local AI inference are planned features.

## Planned features

- Organize PDF documents into collections.
- Add OCR for scanned PDFs and support more complex layouts.
- Ask questions about one or more selected documents.
- Return answers with clickable citations and relevant source passages.
- Say when the selected documents do not provide enough evidence.
- Save conversation history and provide a demo with sample documents.

## Intended approach

StudyMate will use retrieval-augmented generation (RAG). During ingestion, the backend will extract text from each page, split it into passages, and store each passage with its document and page number. At question time, it will retrieve passages from the selected documents and provide them to a locally hosted language model. The backend will return the answer together with references to the passages used.

The stack uses React, TypeScript, Vite, and Tailwind CSS for the frontend; Python and FastAPI for the backend; and PostgreSQL for PDF storage, extracted pages, passages, and the preparation queue. pypdf extracts page text. Vector storage and locally run embedding and language models are planned for retrieval.

## Repository layout

```text
StudyMate/
├── backend/    FastAPI application and Python project configuration
└── frontend/   React, TypeScript, and Vite application
```

## Run with Docker

With Docker running, start the whole app from the repository root:

```sh
docker compose up -d --build --wait
```

Open [StudyMate](http://localhost:5173). Compose builds the frontend and Python image, waits for PostgreSQL, applies database migrations, then starts the API, preparation worker, and frontend. The frontend is served by Nginx, which forwards `/api` to FastAPI. Python, uv, and Node.js are only needed inside the images. Startup dependencies use [Compose health and completion conditions](https://docs.docker.com/compose/how-tos/startup-order/).

The API is also available at `http://127.0.0.1:8000`, including `/health` and `/docs`. Set `STUDYMATE_WEB_PORT`, `STUDYMATE_API_PORT`, or `STUDYMATE_POSTGRES_PORT` in your shell or a root `.env` file to override the default host ports (`5173`, `8000`, and `15432`). All host ports are bound to loopback for local use. Set `POSTGRES_PASSWORD` before creating the database volume to override the local default; the API, migrations, and worker use the same password. Existing volumes retain their original password.

After source or schema changes, run the startup command again to rebuild images and apply migrations. This setup serves a built frontend; use the manual setup below for Vite development with live updates. Run only one preparation worker per database, and stop any manually started API or frontend using the same ports before starting the full stack.

```sh
docker compose logs -f backend worker
docker compose down
```

`docker compose down` stops the app and preserves the named PostgreSQL volume, including uploaded PDFs and preparation results. The `migrate` container exits successfully after applying the schema; this is expected. Services restart automatically when Docker restarts unless explicitly stopped.

## Run locally for development

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

The API listens on `http://127.0.0.1:8000`. Check `http://127.0.0.1:8000/health` for `{"status":"ok"}`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Start the preparation worker in a separate terminal with the same `DATABASE_URL`:

```powershell
cd backend
$env:DATABASE_URL = 'postgresql://studymate:studymate-local@127.0.0.1:15432/studymate'
uv run studymate-worker
```

Use `export DATABASE_URL=...` instead on POSIX shells. Only one worker can run against a database at a time. Keep it running alongside the API; if it is stopped, uploads still succeed and remain queued. After `uv sync` and `uv run studymate-migrate`, existing PDFs are automatically queued as well. Original PDF bytes are preserved.

Start the frontend in another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`. Vite proxies `/api` to the local FastAPI server. In a deployed setup, route `/api` to FastAPI on the same origin as the frontend.

The API provides `POST /api/documents` (multipart field `file`), `GET /api/documents`, `GET /api/documents/{id}/content`, and `DELETE /api/documents/{id}`. Each PDF must be at most 25 MiB. The browser checks type, size, and PDF signature for quick feedback; FastAPI repeats validation, rejects encrypted or malformed PDFs, and stores the original bytes with metadata. This first version is for trusted local single-user use and has no authentication.

## PDF preparation

Uploads include a persistent preparation record in the same transaction. The worker polls PostgreSQL every two seconds when idle, processes one document at a time, and records progress after each page. The document list refreshes while work is pending and displays progress, errors, and a retry button for failed preparations. The worker requeues interrupted attempts when restarted; processing errors require manual retry.

Preparation uses pdfplumber/PDFium locally without AI models or OCR. It orders selectable text geometrically, handles common two-column layouts, and excludes repeated margin text while retaining it for inspection. It extracts ruled and aligned numeric tables, preserves likely equations as text with crops, and renders bitmap/vector graphics with existing captions when identifiable. Classification, table headers, reading order, and caption association are heuristic; inspect warnings and compare with the original. Full-page images preserve evidence when region recovery is uncertain.

Rendering limits the longest image edge to 1,800 pixels, region crops to 128 per page, graphic clustering to 2,000 drawing objects per page, and retained images to 64 MiB per document. Images are staged on temporary disk and published sequentially rather than accumulated in memory. If a limit or rendering failure prevents evidence recovery, the inspector warns and the original PDF remains available.

Select a document to inspect each physical page beside its rendered original. Tables show rows and cells, equations show available symbols and crops, and diagrams show crops with source captions. Use Previous/Next or the physical-page input, and open the PDF directly if rendering fails. Downloads and manual corrections are not part of this version.

Passages never cross physical page boundaries. Plain-text passages target 2,000 Unicode characters with up to 200 characters of overlap. Structured content retains block references: table passages split between rows and repeat available headers; equation text stays together with its crop reference. A single oversized row or equation can exceed the target to preserve its evidence. Plain-text offsets refer to normalized page text; structured passages use null offsets and `content_refs` rather than pretending generated header repetition is one contiguous source range.

Results become available together only after processing completes. States are `queued`, `processing`, `ready`, `ready_with_warnings`, `no_text`, and `failed`. Pages without extractable text remain inspectable but generate no passages. Mixed documents expose useful content with page-specific warnings; wholly textless documents finish as `no_text`. Empty text may indicate a blank page or a scan and does not prove that OCR is needed. Deleting a document also deletes its preparation, published metadata, pages, passages, and images.

Use Reprocess to regenerate completed documents explicitly; upgrades do not automatically reprocess them. Current-attempt state is separate from `published` metadata. Old published results remain visible while a new attempt runs and after failure, and a new usable result replaces them atomically. A rerun that recovers no text does not replace a previously text-bearing publication. Existing completed v1 results remain accessible after migration; reprocess them to get the richer v2 artifacts.

Additional endpoints:

- `POST /api/documents/{id}/prepare` queues explicit preparation/reprocessing (`202`); already queued/running documents return `409`, missing documents `404`.
- `GET /api/documents/{id}/pages` returns normalized text, typed blocks, warnings, `has_text`, and a page-image reference.
- `GET /api/documents/{id}/chunks` returns passages with physical-page references, optional character offsets, and content-block references.
- `GET /api/documents/{id}/assets/{asset_id}` serves published PNG evidence; old replaced or deleted assets return `404`.

Both result endpoints accept `offset` (default 0) and `limit` (default 50, range 1–200), and return `{items, total, offset, limit, published}` in source order. An optional `publication_id` pins requests to the displayed extraction; a replaced publication returns `409`. Results remain available whenever a publication exists, independently of the current attempt. Upload/list metadata includes `preparation` for attempt progress and `published` for the displayed result's ID, version, counts, empty pages, status, and timestamp.

This version prepares English PDFs with selectable text. It does not implement OCR, AI models, guaranteed LaTeX conversion, diagram interpretation, automatic cross-page table merging, embeddings, search, retrieval, or chat. Character-based chunk sizes are independent of a future embedding model's token limits. Representative study PDFs are still needed to assess extraction quality beyond the synthetic fixtures.

## Current checks

```sh
cd frontend
npm run lint
npm run build
```

The backend health endpoint can be checked at `/health` while the server is running.

The PostgreSQL container also creates a separate `studymate_test` database on a fresh volume. To run backend integration tests, set `TEST_DATABASE_URL` to `postgresql://studymate:studymate-local@127.0.0.1:15432/studymate_test`, then run `uv run python -m unittest discover -s tests` from `backend/`. Tests require the separate database and do not touch the app database.
