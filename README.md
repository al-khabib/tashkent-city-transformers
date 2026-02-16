# Tashkent Grid Commander (React + FastAPI RAG)

Executive dashboard for monitoring transformer risk in Tashkent, with:

- Interactive Leaflet map UI (React + Vite + Tailwind)
- Stress simulation controls (temperature, urban growth)
- Analytics + chatbot assistant
- RAG backend (FastAPI + Chroma + FastEmbed embeddings + Groq LLM)

---

## 1) Tech Stack

### Frontend

- React 18 + Vite
- Tailwind CSS
- React Leaflet / Leaflet
- Recharts, framer-motion, lucide-react
- i18next (UZ/RU/EN UI)

### Backend

- FastAPI + Uvicorn/Gunicorn
- LangChain + RetrievalQA
- Chroma vector store (`./chroma_db`)
- FastEmbed embeddings (`BAAI/bge-small-en-v1.5`)
- Groq LLM (`llama3-8b-8192` by default)

---

## 2) Project Structure

```text
.
├── src/                    # React app
├── data/                   # PDF legal documents for ingestion
├── chroma_db/              # Generated vector DB (created by ingest.py)
├── ingest.py               # Builds Chroma DB from PDFs
├── main.py                 # FastAPI backend
├── requirements.txt        # Backend dependencies
└── package.json            # Frontend dependencies/scripts
```

---

## 3) Prerequisites

Install:

- Node.js 18+ and npm
- Python 3.10+ (3.11 recommended)

Check versions:

```bash
node -v
npm -v
python3 --version
```

---

## 4) Environment Variables

Create backend env file:

`server/.env` (or root `.env`)

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama3-8b-8192
ALLOWED_ORIGINS=http://localhost:5173
```

Optional frontend env (`.env.local`):

```env
VITE_API_URL=http://localhost:8000
VITE_API_TIMEOUT_MS=90000
VITE_DEBUG_FLOW=true
```

Notes:

- `GROQ_API_KEY` is required.
- Keep `.env` files out of git.

---

## 5) Local Setup

### A. Install frontend dependencies

```bash
npm install
```

### B. Install backend dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### C. Add legal PDFs

Place your source PDFs in:

```text
./data
```

### D. Build vector database (required for RAG)

```bash
python ingest.py
```

Expected output includes:

- number of loaded PDFs
- number of indexed chunks
- `chroma_db` path

### E. Start backend API

```bash
python main.py
```

Backend runs on:

- `http://localhost:8000`

Health check:

```bash
curl http://localhost:8000/health
```

### F. Start frontend

In another terminal:

```bash
npm run dev
```

Frontend runs on:

- `http://localhost:5173`

---

## 6) Test End-to-End

Quick backend test:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Elektr xavfsizligi bo‘yicha asosiy talablar nima?"}'
```

Expected:

- JSON with `answer`
- no timeout in frontend console

---

## 7) Common Issues & Fixes

### 1) `GROQ_API_KEY is not set`

- Ensure `server/.env` (or root `.env`) contains `GROQ_API_KEY`.
- Restart backend after env changes.

### 2) Chat timeout (e.g. `Timeout: 90s`)

- Increase `VITE_API_TIMEOUT_MS`.
- First request can be slower than subsequent ones.
- Check backend logs with request ID from chat.

### 3) Empty/weak RAG answers

- Re-run ingestion after changing PDFs:
  ```bash
  python ingest.py
  ```
- Confirm `chroma_db` exists and has been regenerated.

### 4) CORS errors

- Set `ALLOWED_ORIGINS` correctly (for local use `http://localhost:5173`).

### 5) Memory pressure on small machines/instances

- Current config already uses lightweight embeddings (`fastembed`) and small chunking.

---

## 8) Useful Commands

```bash
# Frontend production build
npm run build

# Compile-check backend scripts
python3 -m compileall main.py ingest.py

# Re-index documents after updating data
python ingest.py
```

---

## 9) Security Notes

- Never commit real API keys.
- Rotate keys immediately if exposed.
- Keep `.env`, `server/.env` private.

---

## 10) Deployment Notes (Optional)

For Render:

- Build command:
  ```bash
  pip install -r requirements.txt && python ingest.py
  ```
- Start command:
  ```bash
  gunicorn -w 1 -t 120 -k uvicorn.workers.UvicornWorker main:app
  ```

For Netlify frontend:

- Set:
  - `VITE_API_URL=https://<your-render-domain>`
  - optional `VITE_API_TIMEOUT_MS=90000`
