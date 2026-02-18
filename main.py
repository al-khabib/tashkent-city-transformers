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
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_community.llms import Ollama
from pydantic import BaseModel
from sklearn.cluster import KMeans


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


def _detect_language_fast(text: str) -> str:
    if re.search(r"[А-Яа-яЁё]", text):
        return "ru"
    lowered = text.lower()
    uz_markers = ("qanday", "bo'yicha", "uchun", "tuman", "yil", "kerak", "salom")
    if any(marker in lowered for marker in uz_markers):
        return "uz"
    return "en"


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
CSV_PATH = _resolve_path(os.getenv("GRID_DATA_CSV", "tashkent_grid_historic_data.csv"))
MODEL_PATH = _resolve_path(os.getenv("GRID_MODEL_PATH", "grid_load_rf.joblib"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.1:8b")

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
global_future_state: Dict[str, Any] = {}

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


llm = Ollama(
    model=OLLAMA_LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.2,
)

DISTRICT_CENTERS = {
    "yunusabad": [41.3650, 69.2890],
    "chilonzor": [41.2850, 69.2030],
    "mirzo ulugbek": [41.3250, 69.3450],
    "sergeli": [41.2300, 69.2280],
    "shaykhontohur": [41.3250, 69.2450],
    "olmazor": [41.3560, 69.2320],
    "yakkasaroy": [41.2940, 69.2550],
    "bektemir": [41.2360, 69.3350],
}


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
    load_percentage = utilization * 100
    risk_score = max(1, min(10, math.ceil(utilization * 8)))
    if load_gap > 0:
        risk_score = min(10, risk_score + 1)
    risk_level = "Low" if risk_score <= 4 else "Medium" if risk_score <= 7 else "High"

    tp_capacity_mw = float(current.get("avg_tp_capacity_mw", 2.5))
    tps_needed = max(0, math.ceil(load_gap / max(tp_capacity_mw, 0.1)))

    return {
        "district": district,
        "target_date": target.isoformat(),
        "months_ahead": months_ahead,
        "predicted_load_mw": round(predicted_load, 2),
        "current_capacity_mw": round(current_capacity, 2),
        "load_gap_mw": round(load_gap, 2),
        "load_percentage": round(load_percentage, 2),
        "risk_level": risk_level,
        "risk_score": int(risk_score),
        "transformers_needed": int(tps_needed),
        "affecting_factors": {
            "district_rating": float(current["district_rating"]),
            "population_density": float(current["population_density"]),
            "avg_temp": float(current["avg_temp"]),
            "asset_age": float(current["asset_age"]),
            "commercial_infra_count": float(current["commercial_infra_count"]),
            "months_ahead": months_ahead,
        },
    }


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


def translate_to_english(text: str, source_lang: str) -> str:
    if source_lang == "en":
        return text
    prompt = (
        "Translate the following text to English.\n"
        "Return only the translated text, no comments.\n\n"
        f"Source language: {source_lang}\n"
        f"Text: {text}"
    )
    return str(llm.invoke(prompt)).strip()


def translate_from_english(text: str, target_lang: str) -> str:
    if target_lang == "en":
        return text
    prompt = (
        f"Translate the following text from English to {target_lang}.\n"
        "Keep structure and bullet points.\n"
        "Return only translated text.\n\n"
        f"Text: {text}"
    )
    return str(llm.invoke(prompt)).strip()


def explain_prediction_for_mayor(query: str, prediction: Dict[str, Any]) -> str:
    brief_prompt = (
        "You are briefing the Mayor of Tashkent.\n"
        "Turn the prediction numbers into a concise operational warning in English.\n"
        "Use exactly 4 bullet points with clear labels:\n"
        "- Forecast\n"
        "- Capacity Gap\n"
        "- Risk Score (1-10)\n"
        "- TP Action Plan\n"
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


class PredictRequest(BaseModel):
    target_date: str


def _make_suggested_tp_points(district: str, transformers_needed: int, overload_scale: float) -> list[Dict[str, Any]]:
    if transformers_needed <= 0:
        return []
    center = DISTRICT_CENTERS.get(district, [41.3111, 69.2797])
    sample_count = max(10, transformers_needed * 8)
    jitter = 0.007 + min(0.02, overload_scale / 1000)
    points = np.column_stack(
        [
            np.random.normal(center[0], jitter, sample_count),
            np.random.normal(center[1], jitter, sample_count),
        ]
    )
    cluster_count = min(transformers_needed, len(points))
    if cluster_count <= 0:
        return []
    kmeans = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
    kmeans.fit(points)
    centers = kmeans.cluster_centers_
    return [
        {
            "id": f"{district}-tp-{index}",
            "district": district,
            "coordinates": [round(value[0], 6), round(value[1], 6)],
        }
        for index, value in enumerate(centers.tolist(), start=1)
    ]


@app.post("/predict")
async def predict_endpoint(item: PredictRequest, request: Request):
    try:
        district_predictions = []
        suggested_tps = []
        for district in known_districts:
            prediction = predict_grid_load(district, item.target_date)
            district_predictions.append(prediction)
            if prediction["predicted_load_mw"] > prediction["current_capacity_mw"]:
                suggested_tps.extend(
                    _make_suggested_tp_points(
                        district,
                        prediction["transformers_needed"],
                        max(0.0, prediction["load_gap_mw"]),
                    )
                )

        district_prediction_map = {entry["district"]: entry for entry in district_predictions}
        for point in suggested_tps:
            district_prediction = district_prediction_map.get(point["district"], {})
            affecting = district_prediction.get("affecting_factors", {})
            predicted_load = float(district_prediction.get("predicted_load_mw", 0))
            current_capacity = float(district_prediction.get("current_capacity_mw", 0))
            load_gap = float(district_prediction.get("load_gap_mw", 0))
            load_percentage = float(district_prediction.get("load_percentage", 0))
            point["target_date"] = district_prediction.get("target_date", item.target_date)
            point["expected_load_kw"] = round(predicted_load * 1000, 1)
            point["expected_load_mw"] = round(predicted_load, 2)
            point["current_capacity_mw"] = round(current_capacity, 2)
            point["load_gap_mw"] = round(load_gap, 2)
            point["load_percentage"] = round(load_percentage, 2)
            point["transformers_needed"] = int(district_prediction.get("transformers_needed", 0))
            point["why_summary"] = (
                f"By {point['target_date']}, projected demand reaches {point['expected_load_mw']} MW "
                f"against {point['current_capacity_mw']} MW capacity "
                f"({point['load_percentage']}% utilization)."
            )
            point["reasons"] = [
                f"Capacity shortfall: {point['load_gap_mw']} MW.",
                f"Estimated expansion need: {point['transformers_needed']} new transformer(s).",
                (
                    "Main stress drivers: "
                    f"density {int(affecting.get('population_density', 0))}, "
                    f"temperature factor {round(float(affecting.get('avg_temp', 0)), 1)}C, "
                    f"commercial load index {int(affecting.get('commercial_infra_count', 0))}."
                ),
            ]

        global global_future_state
        global_future_state = {
            "target_date": item.target_date,
            "generated_at": datetime.utcnow().isoformat(),
            "district_predictions": district_predictions,
            "suggested_tps": suggested_tps,
            "total_transformers_needed": int(
                sum(entry["transformers_needed"] for entry in district_predictions)
            ),
        }
        return {
            "request_id": request.state.request_id,
            "mode": "prediction",
            "target_date": item.target_date,
            "district_predictions": district_predictions,
            "suggested_tps": suggested_tps,
            "total_transformers_needed": global_future_state["total_transformers_needed"],
        }
    except Exception as error:
        logger.exception("predict_endpoint failed")
        raise HTTPException(
            status_code=400,
            detail={"message": str(error), "request_id": request.state.request_id},
        )


@app.post("/ask")
async def ask_question(item: ChatQuery, request: Request):
    try:
        query = (item.query or item.question or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query is required.")
        context_snapshot = item.context_snapshot or item.context or {}

        user_language = _detect_language_fast(query)
        query_en = translate_to_english(query, user_language)

        future_context = (
            json.dumps(global_future_state, ensure_ascii=True)
            if global_future_state
            else "No future mode prediction has been generated yet."
        )
        answer_en = str(
            llm.invoke(
                "You are now synced with the Map Future Mode.\n"
                "When a date is selected, provide only a concise prediction summary.\n"
                "Do not explain reasons behind suggested TP installations unless the user explicitly asks why.\n"
                "Keep the answer short, practical, and focused on what will happen.\n\n"
                f"Future mode state: {future_context}\n"
                f"Client context snapshot: {json.dumps(context_snapshot, ensure_ascii=True)}\n"
                f"User question: {query_en}\n"
                "Respond with practical guidance for the Mayor."
            )
        ).strip()
        answer = translate_from_english(answer_en, user_language)
        return {
            "answer": answer,
            "request_id": request.state.request_id,
            "mode": "future_chat",
            "user_language": user_language,
            "future_state": global_future_state,
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
        "provider": "ollama-local-predictive",
        "llm_model": OLLAMA_LLM_MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "csv_path": CSV_PATH,
        "model_path": MODEL_PATH,
        "known_districts": known_districts,
        "future_state_loaded": bool(global_future_state),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
