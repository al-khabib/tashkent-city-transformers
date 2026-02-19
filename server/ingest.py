import os
import shutil

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(__file__))


def _load_env() -> None:
    base_dir = _project_root()
    for env_path in (os.path.join(base_dir, ".env"), os.path.join(base_dir, "server", ".env")):
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)


def main() -> None:
    _load_env()

    base_dir = _project_root()
    data_dir = os.path.join(base_dir, "data")
    chroma_dir = os.path.join(base_dir, "chroma_db")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embedding_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data folder not found: {data_dir}")

    loader = PyPDFDirectoryLoader(data_dir)
    docs = loader.load()
    if not docs:
        raise RuntimeError(f"No PDF documents found in: {data_dir}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)

    if os.path.isdir(chroma_dir):
        shutil.rmtree(chroma_dir)

    embeddings = OllamaEmbeddings(model=embedding_model, base_url=ollama_base_url)
    db = Chroma.from_documents(chunks, embeddings, persist_directory=chroma_dir)
    if hasattr(db, "persist"):
        db.persist()

    print(f"Loaded PDFs: {len(docs)}")
    print(f"Chunks indexed: {len(chunks)}")
    print(f"Chroma DB path: {chroma_dir}")


if __name__ == "__main__":
    main()
