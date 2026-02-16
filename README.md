# Tashkent Grid Commander (Local Predictive Backend + React UI)

This project runs a React dashboard with a local FastAPI backend that predicts district grid load and returns Mayor-friendly risk summaries.

Current backend mode is **prediction-focused** (law RAG is not used in runtime flow).

---

## What Runs Where

- Frontend: Vite/React at `http://localhost:5173`
- Backend: FastAPI at `http://127.0.0.1:8000`
- Local LLM + parsing/translation: Ollama (`llama3.1:8b`)
- ML prediction model: `RandomForestRegressor` loaded from `.joblib`

---

## Prerequisites

- Node.js 18+
- Python 3.10+ (3.11 recommended)
- Ollama installed and running

Check:

```bash
node -v
npm -v
python3 --version
ollama --version
```

---

## 1) Install Dependencies

### Frontend

```bash
npm install
```

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2) Prepare Ollama Models

Pull required local models:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Start Ollama (if not already running):

```bash
ollama serve
```

---

## 3) Prepare Prediction Artifacts

Backend requires:

- CSV: `tashkent_grid_historic_data.csv`
- Model: `grid_load_rf.joblib`

If you already have them (for example in `model/`), skip generation and set env paths (section 4).

If you need to generate/train from scratch:

```bash
python generate_mock_data.py
python train_model.py
```

This creates:
- `tashkent_grid_historic_data.csv`
- `grid_load_rf.joblib`

---

## 4) Environment Variables

Create `server/.env` (or root `.env`):

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GRID_DATA_CSV=tashkent_grid_historic_data.csv
GRID_MODEL_PATH=grid_load_rf.joblib
```

If your files are inside `model/`, use:

```env
GRID_DATA_CSV=model/tashkent_grid_historic_data.csv
GRID_MODEL_PATH=model/grid_load_rf.joblib
```

Optional frontend env (`.env.local`):

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_API_TIMEOUT_MS=90000
VITE_DEBUG_FLOW=true
```

---

## 5) Start Backend

```bash
python main.py
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

You should see JSON with:
- `provider: ollama-local-predictive`
- valid `csv_path`
- valid `model_path`

---

## 6) Start Frontend

In another terminal:

```bash
npm run dev
```

Open:
- `http://localhost:5173`

---

## 7) End-to-End Testing

### A) Deterministic prediction endpoint

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"district":"sergeli","target_date":"2027-01-01"}'
```

Expected keys:
- `mode: "prediction"`
- `prediction.risk_score`
- `prediction.transformers_needed`

### B) Chat endpoint (same pipeline used by UI chatbot)

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Predict grid load for Sergeli by 2027-01-01"}'
```

Expected:
- `mode: "prediction"`
- `answer` (human-friendly summary)
- `prediction` (structured numbers)

### C) UI Chat test prompts

- `Predict grid load for Sergeli district by 2027-01-01 and tell me risk score and transformers needed.`
- `Sergeli tumani uchun 2027-01-01 holatiga yuklama prognozini bering.`
- `Сделай прогноз нагрузки для Чиланзара на 2027-12-01.`

---

## 8) Common Issues

### `District stats CSV not found` / `Pre-trained model not found`
- Check `GRID_DATA_CSV` and `GRID_MODEL_PATH` in `server/.env`.
- Use relative paths from project root, e.g. `model/grid_load_rf.joblib`.

### Chat timeout
- Ollama may be cold on first request.
- Increase `VITE_API_TIMEOUT_MS` in `.env.local` (e.g. `120000`).

### Backend starts but responses fail
- Confirm Ollama is running and model exists:
  ```bash
  ollama list
  ```

### CORS error in browser
- Ensure `ALLOWED_ORIGINS` includes `http://localhost:5173`.

---

## 9) Developer Notes

- `ingest.py` exists for document indexing, but prediction runtime does not require it.
- `text.py` is a helper script for manual API ping tests.
- Main runtime entrypoints:
  - Backend: `main.py`
  - Frontend: `src/components/Chatbot.jsx`, `src/App.jsx`

---

## 10) Security

- Never commit real secrets.
- Keep `.env` files private.
- Rotate API keys immediately if exposed.

