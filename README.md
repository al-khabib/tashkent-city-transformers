# Tashkent Grid Commander (Local Predictive Backend + React UI)

This project runs a React dashboard with a local FastAPI backend that predicts district grid load and returns Mayor-friendly risk summaries.

Current backend mode is **prediction-focused** (law RAG is not used in runtime flow).

---

## Project Structure

- `backend/`: FastAPI app package (`app.py`, config, runtime state, services)
- `main.py`: thin compatibility entrypoint (`from backend.app import app`)
- `src/`: React frontend
- `model/`: model training script and optional artifacts
- `data/`: PDF source documents

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
python model/train_model.py
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
DATA_SOURCE_PROVIDER=csv
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GRID_DATA_CSV=tashkent_grid_historic_data.csv
COMPANY_API_BASE_URL=
COMPANY_API_TOKEN=
COMPANY_API_TIMEOUT_S=15
GRID_MODEL_PATH=grid_load_rf.joblib
```

If your files are inside `model/`, use:

```env
GRID_DATA_CSV=model/tashkent_grid_historic_data.csv
GRID_MODEL_PATH=model/grid_load_rf.joblib
```

To use company APIs instead of CSV:

```env
DATA_SOURCE_PROVIDER=company_api
COMPANY_API_BASE_URL=https://your-company-api.example.com
COMPANY_API_TOKEN=your_token_if_required
COMPANY_API_TIMEOUT_S=15
```

Current expected endpoint for historic records is:

- `GET /grid/historic` returning either `[...]` or `{"data":[...]}`
- Required fields per record:
  - `district`, `snapshot_date`, `district_rating`, `population_density`, `avg_temp`, `asset_age`, `commercial_infra_count`, `current_capacity_mw`, `actual_peak_load_mw`

Optional frontend env (`.env.local`):

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_API_TIMEOUT_MS=180000
VITE_DEBUG_FLOW=true
```

---

## 5) Start Backend (Recommended)

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

You should see JSON with:

- `provider: ollama-local-predictive`
- `data_source_provider` (`csv` or `company_api`)
- valid `model_path`

Alternative (also works):

```bash
python main.py
```

## 5.1) Stop Backend

Preferred:

- Press `Ctrl + C` in the terminal running uvicorn.

If process does not exit cleanly, stop by port:

```bash
lsof -ti:8000 | xargs kill -TERM
```

Force kill if needed:

```bash
lsof -ti:8000 | xargs kill -9
```

Optional helper alias (add to `~/.zshrc`):

```bash
alias stopgrid='lsof -ti:8000 | xargs kill -TERM 2>/dev/null || true'
```

Then use:

```bash
stopgrid
```

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
  -d '{"target_date":"2027-01-01"}'
```

Expected keys:

- `mode: "prediction"`
- `district_predictions`
- `total_transformers_needed`

### B) Chat endpoint (same pipeline used by UI chatbot)

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Predict grid load for Sergeli by 2027-01-01"}'
```

Expected:

- `mode: "future_chat"`
- `answer` (human-friendly summary)
- `future_state` (latest prediction context if generated)

### C) UI Chat test prompts

- `Predict grid load for Sergeli district by 2027-01-01 and tell me risk score and transformers needed.`
- `Sergeli tumani uchun 2027-01-01 holatiga yuklama prognozini bering.`
- `Сделай прогноз нагрузки для Чиланзара на 2027-12-01.`

---

## 8) Common Issues

### Data source / model startup errors

- For CSV mode (`DATA_SOURCE_PROVIDER=csv`), check `GRID_DATA_CSV`.
- For company API mode (`DATA_SOURCE_PROVIDER=company_api`), check `COMPANY_API_BASE_URL`, token, and API reachability.
- In all modes, check `GRID_MODEL_PATH` (for example `model/grid_load_rf.joblib`).

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
