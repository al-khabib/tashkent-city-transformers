import json
import logging
import math
import os
import re
import time
import uuid
from datetime import date, datetime
from typing import Any, Dict, Optional

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma
from pydantic import BaseModel


logger = logging.getLogger("grid-backend")
logging.basicConfig(level=logging.INFO)


def _load_env() -> None:
    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, "server", ".env"),
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)


def _safe_json_parse(raw_text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _resolve_base_dir() -> str:
    return os.path.dirname(__file__)


def _resolve_path(filename: str) -> str:
    return os.path.join(_resolve_base_dir(), filename)


def _parse_target_date(target_date: str) -> date:
    if not target_date:
        raise ValueError("target_date is required")
    target_date = target_date.strip().lower()
    if target_date in {"next month", "1 month"}:
        today = date.today()
        month = today.month + 1
        year = today.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        return date(year, month, 1)
    if target_date in {"next year", "1 year"}:
        return date(date.today().year + 1, date.today().month, 1)
    if re.fullmatch(r"\d{4}-\d{2}", target_date):
        return datetime.strptime(f"{target_date}-01", "%Y-%m-%d").date()
    return datetime.strptime(target_date, "%Y-%m-%d").date()


_load_env()

BASE_DIR = _resolve_base_dir()
CHROMA_PATH = _resolve_path("chroma_db")
CSV_PATH = _resolve_path(os.getenv("GRID_DATA_CSV", "tashkent_grid_historic_data.csv"))
MODEL_PATH = _resolve_path(os.getenv("GRID_MODEL_PATH", "grid_load_rf.joblib"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.1:8b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

if not os.path.exists(CSV_PATH):
    raise RuntimeError(f"District stats CSV not found at: {CSV_PATH}")
if not os.path.exists(MODEL_PATH):
    raise RuntimeError(f"Pre-trained model not found at: {MODEL_PATH}")

district_df = pd.read_csv(CSV_PATH)
district_df["district"] = district_df["district"].str.strip().str.lower()
model = joblib.load(MODEL_PATH)
known_districts = sorted(district_df["district"].dropna().unique().tolist())

app = FastAPI(title="Tashkent Local Predictive RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled backend error")
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info("%s %s %s %.2fms", request.method, request.url.path, response.status_code, elapsed_ms)
    response.headers["X-Request-ID"] = request_id
    return response


# --- RAG setup (Ollama + Chroma) ---
embeddings = OllamaEmbeddings(
    model=OLLAMA_EMBED_MODEL,
    base_url=OLLAMA_BASE_URL,
)
db = Chroma(
    persist_directory=CHROMA_PATH,
    embedding_function=embeddings,
)

llm = Ollama(
    model=OLLAMA_LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.2,
)

QA_PROMPT = PromptTemplate(
    template=(
        "You are a Tashkent Grid Safety Expert.\n"
        "You must answer only from the legal context below.\n"
        "If the context is insufficient, say so clearly.\n\n"
        "Legal context:\n{context}\n\n"
        "Question:\n{question}\n\n"
        "Answer:"
    ),
    input_variables=["context", "question"],
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={"k": 3}),
    chain_type_kwargs={"prompt": QA_PROMPT},
)


def predict_grid_load(district: str, target_date: str) -> Dict[str, Any]:
    district_key = district.strip().lower()
    district_rows = district_df[district_df["district"] == district_key]
    if district_rows.empty:
        raise ValueError(f"Unknown district: {district}")

    current = district_rows.sort_values("snapshot_date").iloc[-1]
    target = _parse_target_date(target_date)
    today = date.today()
    months_ahead = max(1, (target.year - today.year) * 12 + (target.month - today.month))

    features = [
        float(current["district_rating"]),
        float(current["population_density"]),
        float(current["avg_temp"]),
        float(current["asset_age"]),
        float(current["commercial_infra_count"]),
        float(months_ahead),
    ]

    predicted_load = float(model.predict([features])[0])
    current_capacity = float(current["current_capacity_mw"])
    load_gap = predicted_load - current_capacity
    utilization = predicted_load / max(current_capacity, 1e-6)
    risk_score = max(1, min(10, math.ceil(utilization * 8)))
    if load_gap > 0:
        risk_score = min(10, risk_score + 1)

    tp_capacity_mw = float(current.get("avg_tp_capacity_mw", 2.5))
    tps_needed = max(0, math.ceil(load_gap / max(tp_capacity_mw, 0.1)))

    return {
        "district": district,
        "target_date": target.isoformat(),
        "months_ahead": months_ahead,
        "predicted_load_mw": round(predicted_load, 2),
        "current_capacity_mw": round(current_capacity, 2),
        "load_gap_mw": round(load_gap, 2),
        "risk_score": int(risk_score),
        "transformers_needed": int(tps_needed),
    }


def route_query_type(query: str) -> str:
    router_prompt = (
        "Classify this user question into one label only: "
        "prediction or law.\n"
        "prediction = forecasting future load/capacity/risk/timeframe.\n"
        "law = legal rules, regulations, standards, compliance.\n\n"
        f"Question: {query}\n"
        "Output JSON only: {\"type\":\"prediction\"} or {\"type\":\"law\"}"
    )
    raw = llm.invoke(router_prompt)
    parsed = _safe_json_parse(str(raw))
    if parsed and parsed.get("type") in {"prediction", "law"}:
        return parsed["type"]
    lower = query.lower()
    if any(token in lower for token in ("forecast", "predict", "2030", "2027", "future", "next year", "load")):
        return "prediction"
    return "law"


def extract_prediction_params(query: str) -> Dict[str, str]:
    parser_prompt = (
        "Extract district and target_date from the request.\n"
        "Known districts: " + ", ".join(known_districts) + ".\n"
        "target_date format: YYYY-MM-DD (or infer reasonable next-month date if absent).\n\n"
        f"Request: {query}\n"
        "Return JSON only: {\"district\":\"...\", \"target_date\":\"YYYY-MM-DD\"}"
    )
    raw = llm.invoke(parser_prompt)
    parsed = _safe_json_parse(str(raw)) or {}
    district = str(parsed.get("district", "")).strip().lower()
    target_date = str(parsed.get("target_date", "")).strip()
    if not district:
        for item in known_districts:
            if item in query.lower():
                district = item
                break
    if not target_date:
        target_date = date.today().replace(day=1).isoformat()
    if not district:
        district = known_districts[0]
    return {"district": district, "target_date": target_date}


def explain_prediction_for_mayor(query: str, prediction: Dict[str, Any]) -> str:
    brief_prompt = (
        "You are briefing the Mayor of Tashkent.\n"
        "Turn the prediction numbers into a concise operational warning.\n"
        "Use 4 bullet points: Forecast, Capacity Gap, Risk Score (1-10), Required TP Actions.\n"
        "Tone: executive, direct, actionable.\n\n"
        f"Original question: {query}\n"
        f"Prediction data: {json.dumps(prediction, ensure_ascii=True)}"
    )
    return str(llm.invoke(brief_prompt)).strip()


class ChatQuery(BaseModel):
    query: Optional[str] = None
    question: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


@app.post("/ask")
async def ask_question(item: ChatQuery, request: Request):
    try:
        query = (item.query or item.question or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query is required.")

        query_type = route_query_type(query)
        if query_type == "prediction":
            params = extract_prediction_params(query)
            prediction = predict_grid_load(params["district"], params["target_date"])
            answer = explain_prediction_for_mayor(query, prediction)
            return {
                "answer": answer,
                "request_id": request.state.request_id,
                "mode": "prediction",
                "prediction": prediction,
            }

        rag_result = qa_chain.invoke({"query": query})
        answer = rag_result.get("result") or rag_result.get("answer") or str(rag_result)
        return {
            "answer": answer,
            "request_id": request.state.request_id,
            "mode": "law",
        }
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("ask_question failed")
        raise HTTPException(
            status_code=500,
            detail={"message": str(error), "request_id": request.state.request_id},
        )


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "provider": "ollama-local",
        "llm_model": OLLAMA_LLM_MODEL,
        "embedding_model": OLLAMA_EMBED_MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "chroma_path": CHROMA_PATH,
        "csv_path": CSV_PATH,
        "model_path": MODEL_PATH,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
