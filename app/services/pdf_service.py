import re
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract text per page with fallback"""
        pages_text = []
        
        # Try pdfplumber first (best quality)
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_text.append({
                            "page": i+1,
                            "text": text.strip(),
                            "source": pdf_path.name
                        })
            if pages_text:
                logger.info(f"pdfplumber extracted {len(pages_text)} pages from {pdf_path.name}")
                return pages_text
        except Exception as e:
            logger.warning(f"pdfplumber failed for {pdf_path.name}: {e}")

        # Fallback PyPDF2
        try:
            import PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text() or ""
                        if text.strip():
                            pages_text.append({
                                "page": i+1,
                                "text": text.strip(),
                                "source": pdf_path.name
                            })
                    except Exception as pe:
                        logger.warning(f"Page {i} extraction failed: {pe}")
                        continue
            if pages_text:
                logger.info(f"PyPDF2 extracted {len(pages_text)} pages from {pdf_path.name}")
                return pages_text
        except Exception as e:
            logger.error(f"PyPDF2 failed for {pdf_path.name}: {e}")

        return pages_text

    def clean_text(self, text: str) -> str:
        """Nettoyage basique"""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'-\s*\n\s*', '', text)
        return text.strip()

    def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Découpage intelligent ~300-500 mots avec overlap"""
        words = text.split()
        chunks = []
        
        if len(words) <= self.chunk_size:
            return [{
                "content": text,
                "metadata": metadata,
                "word_count": len(words)
            }]
        
        start = 0
        chunk_id = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            
            # Try to respect sentence boundaries
            if end < len(words):
                # Look for last sentence end in last 50 words
                last_period = chunk_text.rfind('. ')
                if last_period > len(chunk_text) * 0.7:
                    chunk_text = chunk_text[:last_period+1]
                    # Recalculate end
                    actual_words = len(chunk_text.split())
                    end = start + actual_words
            
            chunks.append({
                "content": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_id": chunk_id,
                    "start_word": start,
                    "end_word": end
                },
                "word_count": len(chunk_text.split())
            })
            
            chunk_id += 1
            if end >= len(words):
                break
            start = end - self.chunk_overlap
        
        return chunks

    def process_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Process complet: extraction + chunking"""
        pages = self.extract_text(pdf_path)
        all_chunks = []
        
        for page_data in pages:
            cleaned = self.clean_text(page_data["text"])
            if len(cleaned.split()) < 20:  # Skip too small
                continue
                
            meta = {
                "source": page_data["source"],
                "page": page_data["page"],
                "pdf_path": str(pdf_path)
            }
            
            chunks = self.chunk_text(cleaned, meta)
            all_chunks.extend(chunks)
        
        logger.info(f"PDF {pdf_path.name}: {len(pages)} pages -> {len(all_chunks)} chunks")
        return all_chunks

    def process_multiple_pdfs(self, pdf_paths: List[Path]) -> Dict[str, Any]:
        """Traite plusieurs PDFs"""
        total_chunks = []
        details = []
        
        for pdf_path in pdf_paths:
            try:
                chunks = self.process_pdf(pdf_path)
                total_chunks.extend(chunks)
                details.append({
                    "file": pdf_path.name,
                    "pages": len(set(c["metadata"]["page"] for c in chunks)) if chunks else 0,
                    "chunks": len(chunks),
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {e}")
                details.append({
                    "file": pdf_path.name,
                    "chunks": 0,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "chunks": total_chunks,
            "details": details,
            "total_chunks": len(total_chunks)
        }
