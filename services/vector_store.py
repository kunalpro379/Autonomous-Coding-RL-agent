from __future__ import annotations

import uuid

import chromadb
from chromadb.utils import embedding_functions

from config.settings import settings


class VectorStoreService:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=str(settings.chroma_path))
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="coding_kb",
            embedding_function=self.ef,
        )

    def add_texts(self, texts: list[str], *, metadatas: list[dict] | None = None) -> None:
        ids = [str(uuid.uuid4()) for _ in texts]
        self.collection.add(ids=ids, documents=texts, metadatas=metadatas)

    def query(self, text: str, k: int = 4) -> str:
        res = self.collection.query(query_texts=[text], n_results=k)
        docs = (res.get("documents") or [[]])[0]
        return "\n\n".join(docs) if docs else ""