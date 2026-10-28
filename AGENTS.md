# AGENTS.md

## Stack
- Backend: FastAPI app `backend.presentation_api:app` (routers: transcription, presentations with `/api` prefix, credits, contact).
- Frontend: Vue 3 + Vite + TypeScript + Tailwind 4.
- Requirements: Python 3.10+, Node 18+, ffmpeg (required for audio conversion).

## Run
```bash
# Backend
source .venv/bin/activate
uvicorn backend.presentation_api:app --port 8000

# Frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

## Env
| Variable | Default | Scope |
|---|---|---|
| `MODEL_API_KEY` | (empty, format `LLM_...`) | Backend only. Never expose in frontend. |
| `META_ASR_URL` | `https://api.meta.ai/v1/asr/transcribe` | Backend |
| `ASR_MODEL` | `muse-voice-transcribe-1.0` | Backend |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Frontend (`frontend/.env`) |

## Conventions
- Conventional Commits in Spanish, one work unit per commit.
- LLM returns plain JSON with layout id in `title_text | title_bullets | text_image | quote`. Slide design lives in `SlideCanvas` / `Slide*.vue`.
- Dedupe realtime transcripts by `turnId` in `useRealtimeTranscription` + `useLivePresentation`.
- 4s debounce before calling the LLM slide-generation endpoint.
- `topic_cleaner.py` produces topic/keywords/cleaned text; `enrich_event` in `realtime_proxy.py` attaches them to realtime events.

## Do not commit
`.env`, `.atl/`, `PROPUESTA_CAMBIOS.md`, `node_modules/`, `dist/`, `__pycache__/`, `.venv/`

## Tests / Build
```bash
pytest backend/test_main.py -v
cd frontend && npm run build  # vue-tsc --noEmit && vite build
```

## Security
- Never expose `MODEL_API_KEY` in frontend code or `VITE_*` vars.
- CORS `*` is MVP-only; restrict origins before production.
