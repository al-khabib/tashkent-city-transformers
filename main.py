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
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
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
    return os.path.join(base_dir, "chroma_db")


_load_env()

CHROMA_PATH = _resolve_chroma_path()
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info("%s %s %s %.2fms", request.method, request.url.path, response.status_code, duration_ms)
    response.headers["X-Request-ID"] = request_id
    return response


# --- RAG setup ---
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

llm = ChatGroq(
    model_name=GROQ_MODEL,
    groq_api_key=GROQ_API_KEY,
    temperature=0.2,
)

QA_PROMPT = PromptTemplate(
    template=(
        "You are a Tashkent Grid Safety Expert.\n"
        "You must answer ONLY using the provided legal context.\n"
        "If the answer is not in the context, state that clearly.\n"
        "Do not invent laws, decrees, or regulations.\n\n"
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

        result = qa_chain.invoke({"query": augmented_query})
        answer = result.get("result") or result.get("answer") or result.get("output_text")
        if not answer:
            answer = str(result)

        return {"answer": answer, "request_id": request.state.request_id}
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
        "provider": "groq-rag",
        "model": GROQ_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "chroma_path": CHROMA_PATH,
        "chroma_exists": os.path.isdir(CHROMA_PATH),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
