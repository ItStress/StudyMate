# Repository Guidelines

## Project Structure & Module Organization

`frontend/` contains the React, TypeScript, Vite, and Tailwind CSS app. `frontend/src/main.tsx` mounts `App.tsx`; feature-specific components, hooks, and types belong together under `frontend/src/features/`. `frontend/src/style.css` imports Tailwind, `frontend/index.html` hosts the app, and `frontend/dist/` is generated build output. The PDF picker, list, and preview use the FastAPI document endpoints. `backend/` contains the Python 3.12+ FastAPI app under `backend/src/studymate/`; `main.py` defines `/health` and mounts the document API. PostgreSQL stores PDF bytes and metadata, and `compose.yaml` provides the local database. Dependency manifests are `frontend/package.json` and `backend/pyproject.toml`, with lockfiles beside them. The root `README.md` describes setup and planned retrieval and chat features.

## Build, Test, and Development Commands

Run commands from the named subdirectory:

- `cd backend && uv sync` installs locked Python dependencies.
- `cd backend && uv run studymate` starts the API at `http://127.0.0.1:8000`; check `/health` or `/docs`.
- `docker compose up -d --wait postgres` starts the local database; set `DATABASE_URL` and run `cd backend && uv run studymate-migrate` before starting the API.
- `cd frontend && npm ci` installs dependencies from `package-lock.json`.
- `cd frontend && npm run dev` starts the Vite development server.
- `cd frontend && npm run lint` runs ESLint on the frontend.
- `cd frontend && npm run build` type-checks with `tsc -b` and creates `dist/`.

## Coding Style & Naming Conventions

Follow the existing TypeScript style: two-space indentation, single-quoted strings, and no semicolons. Use PascalCase for React components, camelCase for variables and functions, and `.tsx` for files containing JSX. Keep TypeScript types explicit where inference is unclear; the app compiler rejects unused locals and parameters. Follow Python's four-space indentation and snake_case functions and modules; add type hints for API return values. Run the frontend lint and build checks before submitting changes. No Python formatter or linter is configured yet.

For frontend work, keep `App.tsx` focused on page composition. Group related UI, types, and behavior by feature; use small components with typed props, and move reusable stateful behavior into custom hooks. Derive values from state instead of duplicating state, and clean up browser resources such as object URLs in effects. Keep user-facing text in English. Style components with Tailwind utility classes, including responsive and interaction states; reserve `style.css` for the Tailwind import and shared theme tokens rather than page-specific CSS rules. Avoid adding a component library or custom CSS when Tailwind utilities suffice.

## Testing Guidelines

For frontend changes, run `npm run lint` and `npm run build`. For backend changes, run `uv run python -m unittest discover -s tests` with `TEST_DATABASE_URL` pointing to the separate PostgreSQL test database, then verify `/health` and changed endpoints. Keep tests near the relevant app and use descriptive names.

## Commit & Pull Request Guidelines

The repository has no commits yet, so no commit-message convention can be inferred. Use short, imperative subjects that name the change, such as `Add document upload endpoint`. In pull requests, summarize behavior, list checks run, link related issues when available, and include screenshots for visible UI changes. Keep generated `dist/`, caches, local environments, and secrets out of commits.
