import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_groq import ChatGroq
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


def _resolve_chroma_path() -> str:
    base_dir = os.path.dirname(__file__)
    primary = os.path.join(base_dir, "chroma_db")
    legacy = os.path.join(base_dir, "server", "chroma_db")
    if os.path.isdir(primary):
        return primary
    if os.path.isdir(legacy):
        return legacy
    return primary


# --- 1. CONFIGURATION ---
_load_env()

CHROMA_PATH = _resolve_chroma_path()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RAG_ENABLED = os.getenv("RAG_ENABLED", "false").strip().lower() not in {"0", "false", "no", "off"}
ALLOWED_ORIGINS = []
for raw_origin in os.getenv("ALLOWED_ORIGINS", "*").split(","):
    origin = raw_origin.strip()
    if origin and origin != "*":
        origin = origin.rstrip("/")
    if origin:
        ALLOWED_ORIGINS.append(origin)

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set. Add it to .env or your environment.")

app = FastAPI(title="Tashkent Grid Advisor API")

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
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception(
            "Unhandled error",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info("%s %s %s %.2fms", request.method, request.url.path, response.status_code, duration_ms)
    response.headers["X-Request-ID"] = request_id
    return response


# --- 2. MODEL INITIALIZATION ---
llm = ChatGroq(
    model_name=GROQ_MODEL,
    groq_api_key=GROQ_API_KEY,
    temperature=0.2,
)

SYSTEM_PROMPT = """
You are the Tashkent City Infrastructure & Energy Strategic Advisor.
Your goal is to provide data-driven advice regarding electrical transformer banks.

Instructions:
1. Be accurate and concise.
2. If you are missing concrete data, clearly say so.
3. Keep the tone professional and actionable.
4. If a regulatory reference is provided in user context, cite it.

IMPORTANT:
- If the user speaks in Uzbek, respond in Uzbek.
- If the user speaks in Russian, respond in Russian.
- If the user speaks in English, you MUST respond in either Uzbek or Russian (default to Russian if unsure).
- DO NOT respond in English.
""".strip()

if RAG_ENABLED:
    logger.warning(
        "RAG_ENABLED=true but Groq-only mode is active. Retrieval is skipped unless a separate embedding/retrieval stack is configured."
    )


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

        augmented_query = query
        current_state = item.context_snapshot or item.context
        if current_state:
            augmented_query += f" [Current App State: {current_state}]"

        response = llm.invoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", augmented_query),
            ]
        )
        answer = getattr(response, "content", str(response))

        payload = {
            "answer": answer,
            "request_id": request.state.request_id,
        }
        if RAG_ENABLED:
            payload["warning"] = "RAG is disabled in Groq-only mode unless embeddings are configured."
        return payload
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("ask_question failed")
        raise HTTPException(
            status_code=500,
            detail={
                "message": str(error),
                "request_id": request.state.request_id,
            },
        )


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "provider": "groq",
        "model": GROQ_MODEL,
        "rag_enabled": RAG_ENABLED,
        "chroma_path": CHROMA_PATH,
        "chroma_exists": os.path.isdir(CHROMA_PATH),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
