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

    predicted_load_mw = float(model.predict([features])[0])
    current_capacity_mw = float(current["current_capacity_mw"])
    
    # Scale to individual transformer level (40 total transformers across 8 districts ≈ 5 per district)
    # Average transformer capacity: 75 kVA = 0.075 MW
    # Per-transformer scaling factor: 0.075 MW / (current_capacity_mw / num_transformers_per_district)
    num_transformers_per_district = 5  # average from _generate_stations_from_csv logic (4-6 range)
    avg_transformer_capacity_mw = 0.075  # 75 kVA average
    
    # Scale the predictions to per-transformer level
    scaling_factor = (num_transformers_per_district * avg_transformer_capacity_mw) / max(current_capacity_mw, 1e-6)
    predicted_load = predicted_load_mw * scaling_factor
    current_capacity = current_capacity_mw * scaling_factor
    
    load_gap = predicted_load - current_capacity
    utilization = predicted_load / max(current_capacity, 1e-6)
    load_percentage = utilization * 100
    risk_score = max(1, min(10, math.ceil(utilization * 8)))
    if load_gap > 0:
        risk_score = min(10, risk_score + 1)
    risk_level = "Low" if risk_score <= 4 else "Medium" if risk_score <= 7 else "High"

    tp_capacity_mw = float(current.get("avg_tp_capacity_mw", 2.5))
    tps_needed = max(0, math.ceil(load_gap / max(tp_capacity_mw * scaling_factor, 0.1)))

    return {
        "district": district,
        "target_date": target.isoformat(),
        "months_ahead": months_ahead,
        "predicted_load_kva": round(predicted_load * 1000, 2),
        "current_capacity_kva": round(current_capacity * 1000, 2),
        "load_gap_kva": round(load_gap * 1000, 2),
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


def _district_factor_trends(district: str) -> Dict[str, float]:
    rows = (
        district_df[district_df["district"] == district]
        .sort_values("snapshot_date")
        .tail(24)
    )
    if len(rows) < 12:
        return {"population_pct": 0.0, "commercial_pct": 0.0}
    recent = rows.tail(12)
    previous = rows.head(len(rows) - 12).tail(12)

    def pct_change(new_val: float, old_val: float) -> float:
        if abs(old_val) < 1e-6:
            return 0.0
        return ((new_val - old_val) / old_val) * 100

    return {
        "population_pct": round(
            pct_change(
                float(recent["population_density"].mean()),
                float(previous["population_density"].mean()),
            ),
            1,
        ),
        "commercial_pct": round(
            pct_change(
                float(recent["commercial_infra_count"].mean()),
                float(previous["commercial_infra_count"].mean()),
            ),
            1,
        ),
    }


def _seasonal_pressure_note(target_date_iso: str) -> str:
    month = datetime.strptime(target_date_iso, "%Y-%m-%d").month
    if month in (6, 7, 8):
        return "Summer cooling demand is expected to increase grid stress."
    if month in (12, 1, 2):
        return "Winter heating demand is expected to increase grid stress."
    return "Baseline seasonal demand still contributes to elevated peak load."


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
    label_counts = np.bincount(kmeans.labels_, minlength=cluster_count)
    total_samples = max(1, int(label_counts.sum()))
    return [
        {
            "id": f"{district}-tp-{index}",
            "district": district,
            "coordinates": [round(value[0], 6), round(value[1], 6)],
            "cluster_share_pct": round((label_counts[index - 1] / total_samples) * 100, 1),
        }
        for index, value in enumerate(centers.tolist(), start=1)
    ]


def _generate_stations_from_csv() -> list[Dict[str, Any]]:
    """Generate transformer stations from CSV data in kVA format."""
    # Standard transformer capacity options in kVA
    CAPACITY_OPTIONS = [50, 100, 160, 200, 240, 300, 400]
    
    stations = []
    station_id = 1
    
    # Generate exactly 20 transformers: 10 green (<50%), 5 yellow (50-80%), 5 red (>80%)
    target_stations = 20
    green_count = 10
    yellow_count = 5
    red_count = 5
    
    status_distribution = ["green"] * green_count + ["yellow"] * yellow_count + ["red"] * red_count
    np.random.shuffle(status_distribution)
    
    status_idx = 0
    
    for district in known_districts:
        if status_idx >= len(status_distribution):
            break
            
        district_data = district_df[district_df["district"] == district].sort_values("snapshot_date")
        if district_data.empty:
            continue
        
        latest = district_data.iloc[-1]
        center = DISTRICT_CENTERS.get(district, [41.3111, 69.2797])
        
        current_load_mw = float(latest.get("actual_peak_load_mw", 50))
        capacity_mw = float(latest.get("current_capacity_mw", 120))
        
        # Calculate how many stations to create for this district
        remaining_stations = target_stations - station_id + 1
        remaining_districts = len([d for d in known_districts if known_districts.index(d) >= known_districts.index(district)])
        num_stations = max(1, remaining_stations // remaining_districts)
        
        if num_stations <= 0:
            break
        
        # Generate history for each station
        history_data = []
        for _, row in district_data.iterrows():
            history_data.append({
                "date": str(row["snapshot_date"]),
                "load": round(float(row["actual_peak_load_mw"]) / capacity_mw * 100, 1),
            })
        
        for i in range(num_stations):
            if status_idx >= len(status_distribution) or station_id > target_stations:
                break
            
            # Get the predetermined status for this station
            target_status = status_distribution[status_idx]
            status_idx += 1
            
            # Select from standard capacity options and convert to Python int
            capacity_kva = int(np.random.choice(CAPACITY_OPTIONS))
            
            # Generate load percentage based on target status
            if target_status == "green":
                load_pct = np.random.uniform(10, 49)  # <50%
            elif target_status == "yellow":
                load_pct = np.random.uniform(50, 79)  # 50-80%
            else:  # red
                load_pct = np.random.uniform(80, 98)  # >80%
            
            station_id_str = f"ts-{station_id:03d}"
            station_id += 1
            
            stations.append({
                "id": station_id_str,
                "name": f"Substation-{district.replace(' ', '-')}-{chr(65 + (i % 26))}",
                "district": district.title(),
                "coordinates": [
                    round(center[0] + np.random.uniform(-0.01, 0.01), 6),
                    round(center[1] + np.random.uniform(-0.01, 0.01), 6),
                ],
                "load_weight": round(load_pct, 1),
                "capacity_kva": capacity_kva,
                "status": target_status,  # Color status: green, yellow, red
                "installDate": int(2023 - np.random.randint(0, 5)),
                "demographic_growth": round(1.0 + np.random.uniform(0.15, 0.35), 2),
                "history": history_data[-24:],  # Last 24 months
            })
    
    return stations


@app.get("/api/stations")
async def get_all_stations(request: Request):
    """Get all transformer stations in kVA format."""
    try:
        stations = _generate_stations_from_csv()
        return {
            "request_id": request.state.request_id,
            "count": len(stations),
            "stations": stations,
        }
    except Exception as error:
        logger.exception("get_all_stations failed")
        raise HTTPException(
            status_code=500,
            detail={"message": str(error), "request_id": request.state.request_id},
        )


@app.get("/api/stations/{district}")
async def get_district_stations(district: str, request: Request):
    """Get transformer stations for a specific district in kVA format."""
    try:
        all_stations = _generate_stations_from_csv()
        district_stations = [s for s in all_stations if s["district"].lower() == district.lower()]
        
        if not district_stations:
            raise HTTPException(
                status_code=404,
                detail={"message": f"District not found: {district}", "request_id": request.state.request_id},
            )
        
        return {
            "request_id": request.state.request_id,
            "district": district,
            "count": len(district_stations),
            "stations": district_stations,
        }
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(f"get_district_stations failed for {district}")
        raise HTTPException(
            status_code=500,
            detail={"message": str(error), "request_id": request.state.request_id},
        )


@app.post("/predict")
async def predict_endpoint(item: PredictRequest, request: Request):
    try:
        # First get all stations to find critical ones
        all_stations = _generate_stations_from_csv()
        
        district_predictions = []
        suggested_tps = []
        
        for district in known_districts:
            prediction = predict_grid_load(district, item.target_date)
            district_predictions.append(prediction)
            
            # Find critical (red) transformers in this district
            critical_transformers = [s for s in all_stations if s["district"] == district.title() and s["status"] == "red"]
            
            # In future prediction mode, always place suggestions next to critical transformers
            # This ensures all critical areas get reinforcement recommendations
            if critical_transformers:
                # Place a suggestion next to each critical transformer
                for i, critical_tf in enumerate(critical_transformers):
                    # Add some jitter to the critical transformer location
                    lat = critical_tf["coordinates"][0] + np.random.uniform(-0.002, 0.002)
                    lon = critical_tf["coordinates"][1] + np.random.uniform(-0.002, 0.002)
                    
                    suggested_tps.append({
                        "id": f"{district}-tp-{i+1}",
                        "district": district,
                        "coordinates": [round(lat, 6), round(lon, 6)],
                        "cluster_share_pct": 20.0,
                    })
            elif prediction["predicted_load_mw"] > prediction["current_capacity_mw"]:
                # If no critical transformers but prediction shows overload, use clustering approach
                transformers_needed = prediction["transformers_needed"]
                months_ahead = prediction.get("months_ahead", 1)
                
                # Scale suggestions based on how far into the future (more months = more suggestions)
                # Linear scaling: 0-6 months = 1x, 6-12 months = 1.5x, 12+ months = 2x
                time_scale_factor = 1.0
                if months_ahead > 12:
                    time_scale_factor = 2.0
                elif months_ahead > 6:
                    time_scale_factor = 1.5
                
                scaled_transformers_needed = max(1, int(transformers_needed * time_scale_factor))
                
                # Fall back to original clustering approach
                suggested_tps.extend(
                    _make_suggested_tp_points(
                        district,
                        scaled_transformers_needed,
                        max(0.0, prediction["load_gap_mw"]),
                    )
                )

        district_prediction_map = {entry["district"]: entry for entry in district_predictions}
        for point in suggested_tps:
            district_prediction = district_prediction_map.get(point["district"], {})
            affecting = district_prediction.get("affecting_factors", {})
            district_trends = _district_factor_trends(point["district"])
            predicted_load_kva = float(district_prediction.get("predicted_load_kva", 0))
            current_capacity_kva = float(district_prediction.get("current_capacity_kva", 0))
            load_gap_kva = float(district_prediction.get("load_gap_kva", 0))
            load_percentage = float(district_prediction.get("load_percentage", 0))
            cluster_share_pct = float(point.get("cluster_share_pct", 0.0))
            
            # Ensure all numeric values are valid
            predicted_load_kva = predicted_load_kva if not (predicted_load_kva != predicted_load_kva) else 0  # NaN check
            current_capacity_kva = current_capacity_kva if not (current_capacity_kva != current_capacity_kva) else 0  # NaN check
            load_gap_kva = load_gap_kva if not (load_gap_kva != load_gap_kva) else 0  # NaN check
            load_percentage = load_percentage if not (load_percentage != load_percentage) else 0  # NaN check
            
            point["target_date"] = district_prediction.get("target_date", item.target_date)
            point["expected_load_kva"] = round(float(predicted_load_kva), 1)
            point["expected_load_mw"] = round(float(predicted_load_kva / 1000), 2)
            point["current_capacity_kva"] = round(float(current_capacity_kva), 1)
            point["current_capacity_mw"] = round(float(current_capacity_kva / 1000), 2)
            point["load_gap_kva"] = round(float(load_gap_kva), 1)
            point["load_gap_mw"] = round(float(load_gap_kva / 1000), 2)
            point["load_percentage"] = round(float(load_percentage), 2)
            point["transformers_needed"] = int(district_prediction.get("transformers_needed", 0))
            point["cluster_load_gap_kva"] = round((cluster_share_pct / 100.0) * max(load_gap_kva, 0.0), 1)
            
            # Build why_summary with safe values
            expected_load_display = int(point["expected_load_kva"]) if point["expected_load_kva"] >= 0 else 0
            current_capacity_display = int(point["current_capacity_kva"]) if point["current_capacity_kva"] >= 0 else 0
            load_pct_display = point["load_percentage"] if point["load_percentage"] >= 0 else 0
            
            point["why_summary"] = (
                f"By {point['target_date']}, projected demand reaches {expected_load_display} kVA "
                f"against {current_capacity_display} kVA capacity "
                f"({load_pct_display}% utilization)."
            )
            # Scale TP counts to transformer level (5 transformers per district average)
            current_tp_count = 5
            overloaded_tp_count = min(
                current_tp_count,
                max(0, int(math.ceil((load_gap_kva / max(current_capacity_kva, 1)) * current_tp_count))),
            )
            point["reasons"] = [
                (
                    f"Capacity shortfall is {point['load_gap_kva']:.0f} kVA on {point['target_date']}; "
                    f"this point covers ~{point['cluster_load_gap_kva']:.0f} kVA of that deficit."
                ),
                (
                    f"In {point['district'].title()}, about {overloaded_tp_count} of {current_tp_count} current transformers "
                    "are likely to run above safe limits at peak hours, increasing outage/shutdown risk."
                ),
                (
                    "Main stress drivers: "
                    f"population trend {district_trends['population_pct']}%, "
                    f"commercial growth {district_trends['commercial_pct']}%, "
                    f"temperature indicator {round(float(affecting.get('avg_temp', 0)), 1)}C. "
                    f"{_seasonal_pressure_note(point['target_date'])}"
                ),
                f"Estimated expansion need for transformer group: {point['transformers_needed']} new unit(s).",
            ]
            
            # Add formatted recommendation summary for display
            point["recommendation"] = (
                f"Proposed Installation: {point['district']}\n\n"
                f"Date: {point['target_date']}\n\n"
                f"Expected Load: {expected_load_display} kVA\n\n"
                f"{point['why_summary']}\n\n"
                + "\n".join(f"{i+1}. {reason}" for i, reason in enumerate(point["reasons"]))
            )

        # Do not artificially cap suggestions; return all generated suggestions
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
