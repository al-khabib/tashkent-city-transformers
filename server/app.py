import asyncio
import json
import logging
import os
import time
import uuid
from requests.exceptions import RequestException

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.config import get_settings
from server.schemas import ChatQuery, PredictRequest
from server.services.prediction_service import build_prediction_response_async
from server.services.station_service import generate_stations_from_csv
from server.state import create_runtime_state

logger = logging.getLogger("grid-backend")
logging.basicConfig(level=logging.INFO)


settings = get_settings()
if not os.path.exists(settings.model_path):
    raise RuntimeError(f"Pre-trained model not found at: {settings.model_path}")

state = create_runtime_state(settings)

app = FastAPI(title="Tashkent Local Predictive RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def preload_current_tps():
    state.current_stations = generate_stations_from_csv(state)


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


@app.get("/api/stations")
async def get_all_stations(request: Request):
    try:
        if not state.current_stations:
            state.current_stations = generate_stations_from_csv(state)
        stations = state.current_stations
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
    try:
        if not state.current_stations:
            state.current_stations = generate_stations_from_csv(state)
        all_stations = state.current_stations
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
        logger.exception("get_district_stations failed for %s", district)
        raise HTTPException(
            status_code=500,
            detail={"message": str(error), "request_id": request.state.request_id},
        )


@app.post("/predict")
async def predict_endpoint(item: PredictRequest, request: Request):
    try:
        if not state.current_stations:
            state.current_stations = generate_stations_from_csv(state)
        all_stations = state.current_stations
        payload = await build_prediction_response_async(state, item.target_date, all_stations)
        state.future_state = payload.pop("future_state")
        return {
            "request_id": request.state.request_id,
            **payload,
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

        future_context = (
            json.dumps(state.future_state, ensure_ascii=True)
            if state.future_state
            else "No future mode prediction has been generated yet."
        )
        prompt = (
            "You are Grid AI Assistant for Tashkent power planning.\n"
            "Always answer in English.\n"
            "Use the future mode state and context snapshot as the source of truth when available.\n"
            "Keep responses practical, concise, and operations-focused.\n"
            "If the user asks for prediction guidance, give a short summary and concrete action.\n"
            "Do not invent missing metrics; say when data is unavailable.\n\n"
            f"Future mode state: {future_context}\n"
            f"Client context snapshot: {json.dumps(context_snapshot, ensure_ascii=True)}\n"
            f"User question: {query}\n"
            "Assistant response:"
        )

        try:
            answer = str(await asyncio.to_thread(state.llm.invoke, prompt)).strip()
        except RequestException as error:
            logger.warning("ask_question failed: Ollama request error: %s", error)
            raise HTTPException(
                status_code=503,
                detail={
                    "message": (
                        f"Ollama is unreachable at {settings.ollama_base_url}. "
                        f"Start Ollama and make sure model '{settings.ollama_llm_model}' is available "
                        "(example: `ollama serve` and `ollama pull "
                        f"{settings.ollama_llm_model}`)."
                    ),
                    "request_id": request.state.request_id,
                    "error": str(error),
                },
            ) from error
        return {
            "answer": answer,
            "request_id": request.state.request_id,
            "mode": "future_chat",
            "language": "en",
            "future_state": state.future_state,
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
        "llm_model": settings.ollama_llm_model,
        "ollama_base_url": settings.ollama_base_url,
        "csv_path": settings.csv_path,
        "model_path": settings.model_path,
        "known_districts": state.known_districts,
        "data_source_provider": state.data_provider_name,
        "future_state_loaded": bool(state.future_state),
    }
