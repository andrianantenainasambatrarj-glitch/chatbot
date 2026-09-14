import logging
from typing import List, Optional
import os

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service d'embedding avec fallbacks:
    1. OpenAI API si clé dispo
    2. sentence-transformers local
    3. TF-IDF sklearn fallback (léger, marche partout)
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.mode = "none"
        self.model = None
        self.vectorizer = None
        self.openai_client = None
        self.dimension = 384  # default for MiniLM
        
        # Try OpenAI first if key available
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=openai_key)
                self.mode = "openai"
                self.dimension = 1536
                logger.info("Embedding mode: OpenAI")
                return
            except Exception as e:
                logger.warning(f"OpenAI embedding init failed: {e}")

        # Try sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.mode = "sentence-transformers"
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Embedding mode: sentence-transformers ({model_name}) dim={self.dimension}")
            return
        except Exception as e:
            logger.warning(f"sentence-transformers not available: {e}")

        # Fallback TF-IDF
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.vectorizer = TfidfVectorizer(max_features=384, stop_words='english')
            self.mode = "tfidf"
            self.dimension = 384
            self._fitted = False
            logger.info("Embedding mode: TF-IDF fallback")
            return
        except Exception as e:
            logger.error(f"All embedding modes failed: {e}")
            self.mode = "hash"
            self.dimension = 384
            logger.info("Embedding mode: simple hash fallback")

    def is_ready(self) -> bool:
        return self.mode != "none"

    def get_mode(self) -> str:
        return self.mode

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        
        if self.mode == "openai" and self.openai_client:
            try:
                # Batch in chunks of 100
                all_embeddings = []
                batch_size = 100
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i+batch_size]
                    resp = self.openai_client.embeddings.create(
                        input=batch,
                        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
                    )
                    all_embeddings.extend([d.embedding for d in resp.data])
                return all_embeddings
            except Exception as e:
                logger.error(f"OpenAI embedding failed: {e}")
                # Fall through to next mode

        if self.mode == "sentence-transformers" and self.model:
            try:
                embeddings = self.model.encode(texts, normalize_embeddings=True)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"ST embedding failed: {e}")

        if self.mode == "tfidf" and self.vectorizer is not None:
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                import numpy as np
                if not self._fitted:
                    # Fit on first batch
                    self.vectorizer.fit(texts)
                    self._fitted = True
                vectors = self.vectorizer.transform(texts).toarray()
                # Pad/truncate to 384
                if vectors.shape[1] < 384:
                    padded = np.zeros((vectors.shape[0], 384))
                    padded[:, :vectors.shape[1]] = vectors
                    vectors = padded
                else:
                    vectors = vectors[:, :384]
                # Normalize
                norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                norms[norms == 0] = 1
                vectors = vectors / norms
                return vectors.tolist()
            except Exception as e:
                logger.error(f"TFIDF embedding failed: {e}")

        # Hash fallback - deterministic pseudo-embedding
        import hashlib
        import numpy as np
        embeddings = []
        for text in texts:
            h = hashlib.md5(text.encode()).hexdigest()
            # Create pseudo vector from hash
            np.random.seed(int(h[:8], 16) % (2**32))
            vec = np.random.randn(self.dimension)
            vec = vec / np.linalg.norm(vec)
            embeddings.append(vec.tolist())
        return embeddings

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]

    def embed_documents(self, docs: List[str]) -> List[List[float]]:
        return self.embed_texts(docs)
