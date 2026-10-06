# StudyMate

StudyMate is a web app for asking questions about your own study materials. Its goal is to turn uploaded PDFs and notes into answers that cite the source document, page, and supporting passage, so every answer can be checked against the original material.

The project is at an early stage. The React frontend uploads PDFs through FastAPI, lists and previews saved documents, and removes them from PostgreSQL. A local worker prepares page text and passages for future retrieval. Its study chat streams explanations through a locally running Ollama model, supports follow-up questions, and offers Stop and Retry controls. PDF retrieval and embeddings are planned features.

## Planned features

- Organize PDF documents into collections.
- Add OCR for scanned PDFs and support more complex layouts.
- Ask questions about one or more selected documents.
- Return answers with clickable citations and relevant source passages.
- Say when the selected documents do not provide enough evidence.
- Save conversation history and provide a demo with sample documents.

## Intended approach

StudyMate will use retrieval-augmented generation (RAG). During ingestion, the backend will extract text from each page, split it into passages, and store each passage with its document and page number. At question time, it will retrieve passages from the selected documents and provide them to a locally hosted language model. The backend will return the answer together with references to the passages used.

The stack uses React, TypeScript, Vite, and Tailwind CSS for the frontend; Python and FastAPI for the backend; PostgreSQL for PDF storage, extracted pages, passages, and the preparation queue; pdfplumber/PDFium for local PDF preparation; and Ollama for local language-model inference. Vector storage and embeddings are planned for retrieval.

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

Chat additionally requires Ollama running with the configured model downloaded; follow the [local language model setup](#local-language-model). Compose does not start Ollama or download models. The containerized API uses `http://host.docker.internal:11434` and `qwen3:4b` by default. Set `OLLAMA_BASE_URL` and `OLLAMA_CHAT_MODEL` in the root `.env` file or shell to override them.

After source or schema changes, run the startup command again to rebuild images and apply migrations. This setup serves a built frontend; use the manual setup below for Vite development with live updates. Run only one preparation worker per database, and stop any manually started API or frontend using the same ports before starting the full stack.

```sh
docker compose logs -f backend worker
docker compose down
```

`docker compose down` stops the app and preserves the named PostgreSQL volume, including uploaded PDFs and preparation results. The `migrate` container exits successfully after applying the schema; this is expected. Services restart automatically when Docker restarts unless explicitly stopped.

## Run locally for development

You will need Docker, Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and a Node.js installation compatible with the Vite version in `frontend/package.json`. Run Ollama either with its [native installation](https://ollama.com/download) or in Docker using the [instructions below](#run-ollama-in-docker). Keep the Docker engine (Docker Desktop on Windows/macOS) and your chosen Ollama service running while using the app. The Docker option does not require installing Ollama on the host.

With a native Ollama installation, download the default model once:

```sh
ollama pull qwen3:4b
```

The model is stored by Ollama outside the repository. For the Docker option, download it inside the container instead, as described below. StudyMate uses this model automatically, so no `OLLAMA_CHAT_MODEL` export is needed for the default setup.

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

On macOS or Linux, run these commands from `backend/` in the same terminal:

```sh
export DATABASE_URL=postgresql://studymate:studymate-local@127.0.0.1:15432/studymate
uv run studymate-migrate
uv run studymate
```

Match the URL port to `STUDYMATE_POSTGRES_PORT` and the password to Docker's `POSTGRES_PASSWORD`. Do not commit real database passwords. Re-run `uv run studymate-migrate` after future schema changes. Leave the backend running and open another terminal for the frontend.

If `uv run studymate-migrate` fails with `ModuleNotFoundError: No module named 'studymate'` on macOS, the editable install may be hidden from Python. Run `uv run --no-editable studymate-migrate` and `uv run --no-editable studymate` instead. This installs a copy of the backend package in the virtual environment, so run `uv sync --no-editable --reinstall-package studymate` after changing backend source files.

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

This version prepares English PDFs with selectable text. It does not implement OCR, AI models, guaranteed LaTeX conversion, diagram interpretation, automatic cross-page table merging, embeddings, search, or retrieval. Study chat runs separately and does not use these prepared results yet. Character-based chunk sizes are independent of a future embedding model's token limits. Representative study PDFs are still needed to assess extraction quality beyond the synthetic fixtures.

## Local language model

StudyMate uses `qwen3:4b` by default. To use another downloaded model, set `OLLAMA_CHAT_MODEL` to its name in the backend shell. The default Ollama URL is `http://127.0.0.1:11434`; set `OLLAMA_BASE_URL` if yours differs. `backend/.env.example` lists these variables. The backend reads shell environment variables; it does not load the example file automatically.

### Run Ollama in Docker

This CPU configuration works on Linux, Windows with Docker Desktop in Linux-container mode, and macOS. On macOS, prefer native Ollama for performance: Docker Desktop does not provide GPU acceleration for Ollama. See the [official Ollama Docker instructions](https://docs.ollama.com/docker) and [GPU limitations](https://github.com/ollama/ollama/blob/main/docs/faq.mdx).

1. Start Docker. If native Ollama is already running, quit it first to free port `11434`.
2. Create and start the container. This single-line command works in PowerShell and macOS/Linux shells:

   ```sh
   docker run -d --name studymate-ollama -p 127.0.0.1:11434:11434 -v studymate-ollama:/root/.ollama ollama/ollama
   ```

3. Download the model once inside the container:

   ```sh
   docker exec studymate-ollama ollama pull qwen3:4b
   ```

   The named volume `studymate-ollama` preserves downloaded models across container restarts and recreation when the same volume is reused. Models downloaded by native Ollama are separate; this container needs its own download.

4. Check the model interactively:

   ```sh
   docker exec -it studymate-ollama ollama run qwen3:4b
   ```

   Ask a short question, then enter `/bye` to leave the interactive chat. Ollama keeps running in the container.

5. Start PostgreSQL, FastAPI, and the frontend using the [local development setup](#run-locally-for-development). With FastAPI running directly on the host, no code or environment changes are needed: it connects to `http://127.0.0.1:11434` and uses `qwen3:4b` by default.

For later sessions, reuse the container rather than running `docker run` again:

```sh
docker start studymate-ollama
```

To stop it or inspect startup errors:

```sh
docker stop studymate-ollama
docker logs studymate-ollama
```

The repository's `compose.yaml` starts PostgreSQL, migrations, FastAPI, the preparation worker, and the frontend; these commands manage Ollama separately. The containerized API defaults to `http://host.docker.internal:11434` to reach Ollama on the host. Override `OLLAMA_BASE_URL` and `OLLAMA_CHAT_MODEL` in the root `.env` file or shell before starting Compose if needed. On Linux, connect the Ollama container to the Compose network with `docker network connect studymate_default studymate-ollama`, then set `OLLAMA_BASE_URL=http://studymate-ollama:11434` before starting Compose. GPU acceleration on compatible Linux/Windows systems requires additional configuration; consult the official Docker instructions linked above.

### Response behavior

The backend calls Ollama asynchronously with thinking mode disabled. The React chat requests a streamed response; the original non-streaming endpoint remains available. If a model still places reasoning inside `<think>...</think>` blocks, the backend removes those blocks before returning the answer. It also handles reasoning prefixes with only a closing `</think>` tag and omits Ollama's separate `thinking` field. A response containing no final answer returns an error instead of displaying reasoning. For streaming, the model is instructed to wrap the final answer in invisible `<answer>` markers: the backend forwards only the answer and filters thinking tags across chunk boundaries. Answer markers are accepted only at the start of output or after a thinking block, so markers quoted inside a legacy reasoning prefix are not mistaken for the final answer. If a model omits these markers, the backend buffers its output and applies the existing filter at completion. This fallback prevents legacy untagged reasoning prefixes from appearing during generation, but that response will appear all at once.

The system instruction makes StudyMate a patient study tutor: it replies in the question's language, explains unfamiliar terms, uses examples when helpful, and adapts to the requested level. It must not claim to read uploaded PDFs or invent page citations. Users can paste a passage for explanation while PDF retrieval is being developed.

The Ollama read timeout is 180 seconds of inactivity; a stream that continues delivering chunks can run longer. The first answer can take longer while Ollama loads the model. If `/api/chat` times out, try a question directly with `ollama run qwen3:4b` (native installation) or `docker exec -it studymate-ollama ollama run qwen3:4b` (Docker) to check whether the model runs on your computer.

## Using the chat

The React chat appears beside the PDF preview on wide screens and below it on smaller screens. Enter or **Send** submits a question; Shift + Enter adds a line. The interface shows **Preparing response…** until answer text arrives, then **Generating response…** as the answer appears progressively. It allows one request at a time. Automatic scrolling follows the response while you are near the bottom; scrolling up lets you read earlier messages. Chat works without uploaded PDFs, and selecting a PDF does not provide its contents to the model.

Conversation history stays in React state until you refresh the page or choose **New chat**. All successful exchanges remain visible, while only the last ten exchanges are sent as context to the model. **Stop** cancels the browser request and keeps any partial answer visible, marked as stopped. **Retry** is available after a failure or stop and repeats that question with the same completed conversation context; it replaces the previous attempt. Failed questions also return to the composer for editing. Partial answers and their questions are excluded from model history. Sending another question replaces the interrupted attempt. **New chat** cancels the pending request and clears the conversation. Closing the upstream connection is attempted when the browser disconnects; cancellation does not guarantee Ollama immediately stops computation.

To check conversational memory, send **My name is Luca**, wait for the answer, then ask **What is my name?**. Choose **New chat** or refresh the page to start a new conversation.

## Chat API

Open `http://127.0.0.1:8000/docs` and call `POST /api/chat`. A simple request is `{"question":"Explain gravity simply"}`. The response is `{"answer":"..."}`. For follow-up questions, include the optional history:

```json
{
  "question": "What is my name?",
  "history": [
    {"role": "user", "content": "My name is Luca."},
    {"role": "assistant", "content": "Hello Luca!"}
  ]
}
```

Only `user` and `assistant` history roles are accepted. The backend prepends its system instruction, retains the last twenty history messages, then appends the current question. Requests containing only `question` remain supported. This endpoint answers general questions; PDF retrieval and citations are planned features.

Blank questions or invalid history return `422`. Ollama HTTP errors and invalid answers return `502`, connection errors or an empty model setting return `503`, and timeouts return `504`.

The React client uses `POST /api/chat/stream` with the same request body. The response is `application/x-ndjson`, one JSON event per line:

```json
{"type":"delta","content":"Gravity "}
{"type":"delta","content":"attracts mass."}
{"type":"done"}
```

Stream failures use `{"type":"error","status":504,"detail":"The language model timed out"}` (or `502`/`503`). Once streaming headers have been sent, the HTTP status stays `200`; the client must inspect events and require `done` before confirming the exchange. Request validation still returns HTTP `422`. Stop and New chat ignore late events and never add incomplete exchanges to history.

To try streaming outside the UI:

```sh
curl -N http://127.0.0.1:8000/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"question":"Explain photosynthesis simply, with an example."}'
```

## Current checks

```sh
cd frontend
npm run lint
npm run build
npm run test:chat
```

The chat client tests use Node's test runner and the existing TypeScript dependency (Node 22+ recommended). They cover chunk decoding, errors, duplicate requests, Stop, Retry, New chat, and late responses with React hooks simulated; they do not replace a browser check.

The backend health endpoint can be checked at `/health` while the server is running. Chat API tests simulate Ollama and cover conversation order, the history limit, role validation, reasoning filtering across chunk boundaries, partial-stream failures, and failure responses. They do not require a running model or database:

```sh
cd backend
uv run python -m unittest discover -s tests -p 'test_chat*.py'
```

The PostgreSQL container also creates a separate `studymate_test` database on a fresh volume. To run backend integration tests, set `TEST_DATABASE_URL` to `postgresql://studymate:studymate-local@127.0.0.1:15432/studymate_test`, then run `uv run python -m unittest discover -s tests` from `backend/`. Tests require the separate database and do not touch the app database.

If using the macOS installation workaround, add `--no-editable` to these `uv run` test commands. Before testing changes to backend source files, refresh the installed copy with `uv sync --no-editable --reinstall-package studymate`.


For a manual chat check, send a study question and confirm progressive text appears, then try **Stop** followed by **Retry**. Ask about an uploaded PDF: the assistant should explain it cannot access the file yet and ask for the passage. Paste a short passage and ask for a simpler explanation. Also try **New chat** during generation and confirm no late answer appears.
