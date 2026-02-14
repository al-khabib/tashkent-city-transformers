import os
import shutil

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _load_env() -> None:
    base_dir = os.path.dirname(__file__)
    for env_path in (os.path.join(base_dir, ".env"), os.path.join(base_dir, "server", ".env")):
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)


def main() -> None:
    _load_env()

    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, "data")
    chroma_dir = os.path.join(base_dir, "chroma_db")
    embedding_model = "BAAI/bge-small-en-v1.5"

    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data folder not found: {data_dir}")

    loader = PyPDFDirectoryLoader(data_dir)
    docs = loader.load()
    if not docs:
        raise RuntimeError(f"No PDF documents found in: {data_dir}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    if os.path.isdir(chroma_dir):
        shutil.rmtree(chroma_dir)

    embeddings = FastEmbedEmbeddings(model_name=embedding_model)
    db = Chroma.from_documents(chunks, embeddings, persist_directory=chroma_dir)
    if hasattr(db, "persist"):
        db.persist()

    print(f"Loaded PDFs: {len(docs)}")
    print(f"Chunks indexed: {len(chunks)}")
    print(f"Chroma DB path: {chroma_dir}")


if __name__ == "__main__":
    main()
