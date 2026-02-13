import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# --- 1. CONFIGURATION ---
load_dotenv()

CHROMA_PATH = "./chroma_db"
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
LLM_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set. Add it to your environment or .env file.")

app = FastAPI(title="Tashkent Grid Advisor API")

# Allow React frontend (usually port 5173 or 3000) to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your specific domain
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. MODEL INITIALIZATION ---
# Initialize embeddings and vector store (no Ollama dependency)
embeddings = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)
db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

# Initialize Groq LLM
llm = ChatGroq(model_name=LLM_MODEL, groq_api_key=GROQ_API_KEY, temperature=0.2)

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

Context: {context}
Question: {question}


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
    return {"status": "online", "model": LLM_MODEL, "provider": "groq", "embedding_model": EMBED_MODEL}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
