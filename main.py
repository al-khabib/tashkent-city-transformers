import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
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
LLM_MODEL = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("GOOGLE_EMBED_MODEL", "models/text-embedding-004")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
ALLOWED_ORIGINS = []
for raw_origin in os.getenv("ALLOWED_ORIGINS", "*").split(","):
    origin = raw_origin.strip()
    if origin and origin != "*":
        origin = origin.rstrip("/")
    if origin:
        ALLOWED_ORIGINS.append(origin)

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env or your environment.")

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
    logger.info(
        "%s %s %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response

# --- 2. MODEL INITIALIZATION ---
embeddings = GoogleGenerativeAIEmbeddings(
    model=EMBED_MODEL,
    google_api_key=GEMINI_API_KEY,
)
db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    google_api_key=GEMINI_API_KEY,
    temperature=0.2,
)

template = """
You are the Tashkent City Infrastructure & Energy Strategic Advisor.
Your goal is to provide data-driven advice regarding electrical transformer banks.

Context: {context}
Question: {question}

Instructions:
1. Use ONLY the provided context to answer.
2. If the context mentions a Presidential Decree (e.g., PP-444), cite it specifically.
3. If you don't know the answer based on the context, say you don't have that specific data.
4. Keep the tone professional, authoritative, and concise.

IMPORTANT:
- If the user speaks in Uzbek, respond in Uzbek.
- If the user speaks in Russian, respond in Russian.
- If the user speaks in English, you MUST respond in either Uzbek or Russian (default to Russian if unsure).
- DO NOT respond in English.

Answer:"""

QA_PROMPT = PromptTemplate(
    template=template,
    input_variables=["context", "question"],
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={"k": 3}),
    chain_type_kwargs={"prompt": QA_PROMPT},
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
            state_str = f" [Current App State: {current_state}]"
            augmented_query += state_str

        response = qa_chain.invoke({"query": augmented_query})
        answer = response.get("result") or response.get("answer") or response.get("output_text")
        if not answer:
            answer = str(response)
        return {"answer": answer, "request_id": request.state.request_id}
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
        "provider": "google-ai-studio",
        "model": LLM_MODEL,
        "embedding_model": EMBED_MODEL,
        "chroma_path": CHROMA_PATH,
        "chroma_exists": os.path.isdir(CHROMA_PATH),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
