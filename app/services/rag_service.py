import logging
from pathlib import Path
from typing import List, Dict, Any

from .pdf_service import PDFService
from .vector_store import VectorStoreService

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self, pdf_service: PDFService, vector_store: VectorStoreService):
        self.pdf_service = pdf_service
        self.vector_store = vector_store

    def ingest_pdfs(self, pdf_paths: List[Path]) -> Dict[str, Any]:
        """Ingestion complète"""
        logger.info(f"Starting ingestion of {len(pdf_paths)} PDFs")
        
        # Process PDFs
        result = self.pdf_service.process_multiple_pdfs(pdf_paths)
        chunks = result["chunks"]
        
        if not chunks:
            return {
                "success": False,
                "message": "Aucun contenu extrait des PDFs",
                "files_processed": 0,
                "chunks_created": 0,
                "details": result["details"]
            }
        
        # Add to vector store
        added = self.vector_store.add_documents(chunks)
        
        return {
            "success": True,
            "message": f"{len(pdf_paths)} PDFs traités, {added} chunks ajoutés",
            "files_processed": len(pdf_paths),
            "chunks_created": added,
            "details": result["details"]
        }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Recherche RAG"""
        if not query.strip():
            return []
        
        # Enrich query for trading context
        enriched_query = f"analyse technique trading {query}"
        
        results = self.vector_store.query(enriched_query, top_k=top_k)
        return results

    def search_from_vision(self, vision_analysis: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """Construit une requête à partir de l'analyse vision"""
        parts = []
        
        if vision_analysis.get("description"):
            parts.append(vision_analysis["description"][:500])
        
        patterns = vision_analysis.get("patterns_detected", [])
        if patterns:
            parts.append(f"patterns: {', '.join(patterns)}")
        
        trend = vision_analysis.get("trend", "")
        if trend:
            parts.append(f"tendance {trend}")
        
        if vision_analysis.get("key_observations"):
            parts.append(vision_analysis["key_observations"][:300])
        
        query = " ".join(parts)
        if not query:
            query = "analyse technique trading pattern support résistance"
        
        return self.search(query, top_k=top_k)

    def get_status(self) -> Dict[str, Any]:
        count = self.vector_store.count()
        sources = self.vector_store.list_sources()
        return {
            "total_chunks": count,
            "sources": sources,
            "total_documents": len(sources)
        }
