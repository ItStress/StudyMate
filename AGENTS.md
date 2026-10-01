# Repository Guidelines

## Project Structure & Module Organization

`frontend/` contains the React, TypeScript, and Vite app. Its entry point is `frontend/src/main.tsx`; `frontend/index.html` hosts it, and `frontend/dist/` is generated build output. `backend/` contains the Python 3.12+ FastAPI app under `backend/src/studymate/`; `main.py` defines the current `/health` endpoint. Dependency manifests are `frontend/package.json` and `backend/pyproject.toml`, with lockfiles beside them. The root `README.md` describes the planned product. Upload, retrieval, chat, and database features are plans, not current modules. There are no test or source asset directories yet.

## Build, Test, and Development Commands

Run commands from the named subdirectory:

- `cd backend && uv sync` installs locked Python dependencies.
- `cd backend && uv run studymate` starts the API at `http://127.0.0.1:8000`; check `/health` or `/docs`.
- `cd frontend && npm ci` installs dependencies from `package-lock.json`.
- `cd frontend && npm run dev` starts the Vite development server.
- `cd frontend && npm run lint` runs ESLint on the frontend.
- `cd frontend && npm run build` type-checks with `tsc -b` and creates `dist/`.

## Coding Style & Naming Conventions

Follow the existing TypeScript style: two-space indentation, single-quoted strings, and no semicolons. Use PascalCase for React components, camelCase for variables and functions, and `.tsx` for files containing JSX. Keep TypeScript types explicit where inference is unclear; the app compiler rejects unused locals and parameters. Follow Python's four-space indentation and snake_case functions and modules; add type hints for API return values. Run the frontend lint and build checks before submitting changes. No Python formatter or linter is configured yet.

## Testing Guidelines

No automated test framework or coverage threshold is configured. For frontend changes, run `npm run lint` and `npm run build`; for backend changes, run the app and verify `/health` plus any changed endpoints. When introducing tests, place them near the relevant app (`frontend/` or `backend/`), use descriptive names such as `test_health.py`, and document the new test command in its package configuration.

## Commit & Pull Request Guidelines

The repository has no commits yet, so no commit-message convention can be inferred. Use short, imperative subjects that name the change, such as `Add document upload endpoint`. In pull requests, summarize behavior, list checks run, link related issues when available, and include screenshots for visible UI changes. Keep generated `dist/`, caches, local environments, and secrets out of commits.
