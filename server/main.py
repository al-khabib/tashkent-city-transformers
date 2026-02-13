import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# --- 1. CONFIGURATION ---
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_PATH)

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
LLM_MODEL = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("GOOGLE_EMBED_MODEL", "models/text-embedding-004")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Add it to server/.env or your environment.")

app = FastAPI(title="Tashkent Grid Advisor API")

# Allow React frontend (usually port 5173 or 3000) to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # In production, set ALLOWED_ORIGINS to explicit domains.
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. MODEL INITIALIZATION ---
# Google AI Studio embeddings + vector store
embeddings = GoogleGenerativeAIEmbeddings(
    model=EMBED_MODEL,
    google_api_key=GEMINI_API_KEY,
)
db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

# Google AI Studio LLM
llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    google_api_key=GEMINI_API_KEY,
    temperature=0.2,
)

# Custom System Prompt for the Mayor's Advisor
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
    template=template, input_variables=["context", "question"]
)

# Create the RAG Chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={"k": 3}), # Retrieve top 3 relevant chunks
    chain_type_kwargs={"prompt": QA_PROMPT}
)

# --- 3. API ENDPOINTS ---
class ChatQuery(BaseModel):
    query: Optional[str] = None
    question: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None

@app.post("/ask")
async def ask_question(item: ChatQuery):
    try:
        query = (item.query or item.question or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query is required.")

        # If the frontend sends current app state (e.g., Winter Stress = -20C),
        # we can append it to the query for "Real-time" awareness.
        augmented_query = query
        current_state = item.context_snapshot or item.context
        if current_state:
            state_str = f" [Current App State: {current_state}]"
            augmented_query += state_str

        response = qa_chain.invoke({"query": augmented_query})
        return {"answer": response["result"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "provider": "google-ai-studio",
        "model": LLM_MODEL,
        "embedding_model": EMBED_MODEL,
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
