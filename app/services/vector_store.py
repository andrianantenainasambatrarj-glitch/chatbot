import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)

class VectorStoreService:
    def __init__(self, persist_dir: Path, embedding_service, collection_name: str = "trading_knowledge"):
        self.persist_dir = persist_dir
        self.embedding_service = embedding_service
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self.mode = "chroma"
        
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            self.client = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Try to get or create collection
            # Use custom embedding function if OpenAI
            if embedding_service.get_mode() == "openai":
                # For OpenAI we will handle embeddings manually
                self.collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            else:
                # For local embeddings, let chroma handle or we provide
                self.collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            
            logger.info(f"ChromaDB initialized at {persist_dir}, collection {collection_name}")
            
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}, using in-memory fallback")
            self.mode = "memory"
            self.memory_store: List[Dict[str, Any]] = []

    def add_documents(self, chunks: List[Dict[str, Any]]) -> int:
        if not chunks:
            return 0
            
        if self.mode == "memory":
            for chunk in chunks:
                embedding = self.embedding_service.embed_texts([chunk["content"]])[0]
                self.memory_store.append({
                    "id": str(uuid.uuid4()),
                    "content": chunk["content"],
                    "metadata": chunk["metadata"],
                    "embedding": embedding
                })
            return len(chunks)

        # Chroma path
        try:
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            contents = [c["content"] for c in chunks]
            all_embeddings = self.embedding_service.embed_texts(contents)
            
            for i, chunk in enumerate(chunks):
                ids.append(f"{chunk['metadata'].get('source','doc')}_{chunk['metadata'].get('page',0)}_{chunk['metadata'].get('chunk_id',i)}_{uuid.uuid4().hex[:8]}")
                documents.append(chunk["content"])
                # Chroma metadata must be flat and simple
                meta = {
                    "source": str(chunk["metadata"].get("source", "unknown"))[:200],
                    "page": int(chunk["metadata"].get("page", 0)),
                    "chunk_id": int(chunk["metadata"].get("chunk_id", 0))
                }
                metadatas.append(meta)
                embeddings.append(all_embeddings[i])
            
            # Add in batches of 100
            batch_size = 100
            total_added = 0
            for j in range(0, len(ids), batch_size):
                self.collection.add(
                    ids=ids[j:j+batch_size],
                    documents=documents[j:j+batch_size],
                    metadatas=metadatas[j:j+batch_size],
                    embeddings=embeddings[j:j+batch_size]
                )
                total_added += len(ids[j:j+batch_size])
            
            logger.info(f"Added {total_added} chunks to Chroma")
            return total_added
            
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            # Fallback to memory
            self.mode = "memory"
            self.memory_store = []
            return self.add_documents(chunks)

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.mode == "memory":
            if not self.memory_store:
                return []
            import numpy as np
            query_emb = np.array(self.embedding_service.embed_query(query_text))
            results = []
            for doc in self.memory_store:
                doc_emb = np.array(doc["embedding"])
                # cosine similarity
                sim = float(np.dot(query_emb, doc_emb))
                results.append({
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "score": sim,
                    "source": doc["metadata"].get("source", "unknown"),
                    "page": doc["metadata"].get("page")
                })
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        try:
            query_emb = self.embedding_service.embed_query(query_text)
            results = self.collection.query(
                query_embeddings=[query_emb],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            formatted = []
            if results["documents"] and len(results["documents"][0]) > 0:
                for i in range(len(results["documents"][0])):
                    doc = results["documents"][0][i]
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    dist = results["distances"][0][i] if results["distances"] else 0
                    # Convert distance to similarity score (cosine distance -> similarity)
                    score = 1 - dist if dist is not None else 0
                    formatted.append({
                        "content": doc,
                        "metadata": meta,
                        "score": score,
                        "source": meta.get("source", "unknown"),
                        "page": meta.get("page")
                    })
            return formatted
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []

    def count(self) -> int:
        if self.mode == "memory":
            return len(self.memory_store)
        try:
            return self.collection.count()
        except:
            return 0

    def clear(self):
        if self.mode == "memory":
            self.memory_store = []
            return
        try:
            # Delete collection and recreate
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Collection cleared")
        except Exception as e:
            logger.error(f"Clear failed: {e}")

    def list_sources(self) -> List[str]:
        if self.mode == "memory":
            return list(set(d["metadata"].get("source","") for d in self.memory_store))
        try:
            # Get all metadatas (limited)
            data = self.collection.get(limit=10000, include=["metadatas"])
            sources = set()
            for meta in data.get("metadatas", []):
                if meta and "source" in meta:
                    sources.add(meta["source"])
            return list(sources)
        except:
            return []
