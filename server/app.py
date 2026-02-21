import asyncio
import json
import logging
import os
import queue
import threading
import time
import uuid
from requests.exceptions import RequestException

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.config import get_settings
from server.schemas import ChatQuery, PredictRequest
from server.services.prediction_service import PredictionCancelledError, build_prediction_response
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

shutdown_event = threading.Event()


def close_runtime_resources() -> None:
    """Best-effort cleanup for model, vector DB clients, and LLM clients."""
    # Chroma-like handles (if present in runtime state or provider internals).
    for attr_name in ("chroma_client", "_chroma_client", "vector_store", "vectorstore", "retriever"):
        resource = getattr(state, attr_name, None)
        if resource is None:
            continue
        close_fn = getattr(resource, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                logger.exception("Failed to close runtime resource: %s", attr_name)

    # Model handles.
    model = getattr(state, "model", None)
    if model is not None:
        close_fn = getattr(model, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                logger.exception("Failed to close model handle")
        state.model = None

    # LLM client handles.
    llm = getattr(state, "llm", None)
    if llm is not None:
        for client_attr in ("client", "_client"):
            client = getattr(llm, client_attr, None)
            close_fn = getattr(client, "close", None) if client is not None else None
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    logger.exception("Failed to close LLM client handle")


@app.on_event("startup")
async def startup_event():
    shutdown_event.clear()


@app.on_event("shutdown")
async def shutdown_event_handler():
    shutdown_event.set()
    close_runtime_resources()


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
        stations = generate_stations_from_csv(state)
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
        all_stations = generate_stations_from_csv(state)
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
    cancel_event = threading.Event()
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _prediction_worker() -> None:
        try:
            payload = build_prediction_response(
                state,
                item.target_date,
                all_stations,
                lambda: cancel_event.is_set() or shutdown_event.is_set(),
            )
            result_queue.put(("ok", payload))
        except Exception as error:
            result_queue.put(("error", error))

    try:
        all_stations = generate_stations_from_csv(state)
        worker = threading.Thread(target=_prediction_worker, name="predict-worker", daemon=True)
        worker.start()

        while True:
            if await request.is_disconnected() or shutdown_event.is_set():
                logger.info("predict_endpoint cancelled due to disconnect/shutdown")
                cancel_event.set()
                raise PredictionCancelledError("Prediction cancelled by disconnect/shutdown")

            try:
                status, result = result_queue.get_nowait()
                if status == "ok":
                    payload = result
                    break
                raise result
            except queue.Empty:
                pass
            await asyncio.sleep(0.1)
        state.future_state = payload.pop("future_state")
        return {
            "request_id": request.state.request_id,
            **payload,
        }
    except PredictionCancelledError:
        raise HTTPException(
            status_code=499,
            detail={"message": "Prediction request cancelled", "request_id": request.state.request_id},
        )
    except asyncio.CancelledError:
        cancel_event.set()
        raise
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
