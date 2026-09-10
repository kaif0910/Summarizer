import os
import logging
from typing import Any, Dict, List, Optional
import chromadb

logger = logging.getLogger(__name__)

CHROMA_PATH = os.path.join(os.getcwd(), "chroma_db")
os.makedirs(CHROMA_PATH, exist_ok=True)

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="recording_sessions")


class VectorService:
    @staticmethod
    def index_session(
        session_id: str,
        text: str,
        date_str: str,
        metadata_extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Embeds and indexes a session's transcript or summary into ChromaDB
        along with metadata (session_id, date).
        """
        if not text or not text.strip():
            logger.warning(f"Skipping ChromaDB indexing for session {session_id}: empty text.")
            return

        meta: Dict[str, Any] = {
            "session_id": str(session_id),
            "date": date_str,
        }

        if metadata_extra:
            for k, v in metadata_extra.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v

        collection.upsert(
            ids=[str(session_id)],
            documents=[text],
            metadatas=[meta]
        )
        logger.info(f"Indexed session {session_id} in ChromaDB collection.")

    @staticmethod
    def search_sessions(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Performs semantic vector search across indexed past sessions in ChromaDB.
        """
        if not query or not query.strip():
            return []

        results = collection.query(
            query_texts=[query],
            n_results=limit
        )

        formatted_results: List[Dict[str, Any]] = []

        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if ("metadatas" in results and results["metadatas"]) else [{}] * len(docs)
            ids = results["ids"][0] if ("ids" in results and results["ids"]) else [""] * len(docs)
            distances = (
                results["distances"][0]
                if ("distances" in results and results["distances"])
                else [None] * len(docs)
            )

            for i in range(len(docs)):
                formatted_results.append({
                    "session_id": metas[i].get("session_id", ids[i]),
                    "document": docs[i],
                    "metadata": metas[i],
                    "distance": distances[i] if i < len(distances) else None
                })

        return formatted_results
