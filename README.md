# Transcripcion de voz en vivo

Proxy simple para transcribir voz en español con la API de Meta Muse Voice Transcribe,
sin exponer la API key en el frontend.

## Arquitectura

- **Backend (FastAPI):** recibe el audio del navegador, lo convierte a WAV mono
  16-bit PCM 24 kHz con ffmpeg y lo reenvia a Meta. La key `MODEL_API_KEY`
  solo existe en el backend.
- **Frontend (Vue 3 + Vite + TypeScript):** micrófono, botón Transcribir y texto. Nunca maneja la key.

Motor: `muse-voice-transcribe-1.0`, endpoint `POST https://api.meta.ai/v1/asr/transcribe`.
Modo `PUSH_TO_TALK`, sesgo de idioma español, sin diarizacion.

## Requisitos

- Python 3.10+
- Node.js 18+ y npm
- ffmpeg (obligatorio para convertir el audio del navegador a WAV 24 kHz):
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
- Una API key de Meta con formato `LLM_...`

## Instalacion

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install pytest
cp .env.example .env
# Edita .env y coloca tu key real en MODEL_API_KEY
```

Frontend:

```bash
cd frontend
cp .env.example .env
# Edita .env y ajusta VITE_API_BASE_URL si el backend no corre en http://localhost:8000
npm install
```

## Como correrlo

Terminal 1 (backend):

```bash
source .venv/bin/activate
uvicorn backend.presentation_api:app --port 8000
```

Terminal 2 (frontend):

```bash
cd frontend
npm run dev
```

Abre el navegador en http://localhost:5173, graba tu voz y presiona **Transcribir**.

> Nota: el micrófono requiere servir la app en `localhost` o bajo HTTPS.
> Safari no soporta `audio/webm`; en ese caso el frontend graba en MP4
> (`audio/mp4`) y el backend lo convierte igual con ffmpeg.

## Como conseguir la key

1. Entra al portal de desarrolladores de Meta y crea un proyecto con acceso a Muse Voice.
2. Genera una API key (empieza con `LLM_...`).
3. Copiala en `.env` como `MODEL_API_KEY=LLM_...`. Nunca la pongas en el frontend.

## Limites y costo

- Tamaño maximo por archivo: **32 MB** (el backend responde 413 si se supera).
- Duracion maxima aproximada: **10 minutos** por pedido.
- Costo de referencia: **$0.18 por hora** de audio transcrito.
- Formato requerido por Meta: **WAV**. El navegador suele enviar otro formato,
  por eso el backend lo convierte automaticamente con ffmpeg.

## Variables de entorno

| Variable        | Default                                    | Descripcion                  |
|---------------|--------------------------------------------|------------------------------|
| MODEL_API_KEY | (vacia)                                    | Key `LLM_...`, solo backend |
| META_ASR_URL  | https://api.meta.ai/v1/asr/transcribe      | Endpoint de Meta             |
| ASR_MODEL     | muse-voice-transcribe-1.0                  | Modelo de transcripcion      |
| VITE_API_BASE_URL | http://localhost:8000                  | URL del backend (frontend, archivo `frontend/.env`) |

## Tests

```bash
source .venv/bin/activate
pytest backend/test_main.py -v
```
# live-presentation-ia
