import os
import logging
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import shutil
import uuid

from app.config import settings
from app.config.styles import list_styles, get_style
from app.services.pdf_service import PDFService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.vision_service import VisionService
from app.services.rag_service import RAGService
from app.services.analysis_service import AnalysisService
from app.models.schemas import PDFIngestResponse, KnowledgeStatus, HealthResponse
from app.utils.helpers import is_allowed_pdf, is_allowed_image, save_uploaded_file

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Init FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="IA Trading Graph Analyzer - RAG + Vision LLM"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Initialize services (lazy singleton)
_embedding_service = None
_vector_store = None
_pdf_service = None
_vision_service = None
_rag_service = None
_analysis_service = None

def get_embedding_service():
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(model_name=settings.embedding_model_name)
    return _embedding_service

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService(
            persist_dir=settings.chroma_dir,
            embedding_service=get_embedding_service(),
            collection_name="trading_knowledge"
        )
    return _vector_store

def get_pdf_service():
    global _pdf_service
    if _pdf_service is None:
        _pdf_service = PDFService(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    return _pdf_service

def get_vision_service():
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service

def get_rag_service():
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(
            pdf_service=get_pdf_service(),
            vector_store=get_vector_store()
        )
    return _rag_service

def get_analysis_service():
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = AnalysisService(
            rag_service=get_rag_service(),
            vision_service=get_vision_service()
        )
    return _analysis_service

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "settings": settings})
    except TypeError:
        # Fallback for older starlette
        return templates.TemplateResponse("index.html", {"request": request, "settings": settings})

@app.get("/api/health", response_model=HealthResponse)
async def health():
    emb = get_embedding_service()
    vs = get_vector_store()
    return HealthResponse(
        status="ok",
        version=settings.version,
        chroma_ready=vs.count() >= 0,
        embedding_ready=emb.is_ready()
    )

@app.get("/api/knowledge/status", response_model=KnowledgeStatus)
async def knowledge_status():
    vs = get_vector_store()
    emb = get_embedding_service()
    vision = get_vision_service()
    status = get_rag_service().get_status()
    
    return KnowledgeStatus(
        total_documents=status["total_documents"],
        total_chunks=status["total_chunks"],
        collection_name="trading_knowledge",
        embedding_mode=emb.get_mode(),
        llm_providers=vision.get_available_providers()
    )

@app.post("/api/upload-pdfs", response_model=PDFIngestResponse)
async def upload_pdfs(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")
    
    saved_paths = []
    for file in files:
        if not is_allowed_pdf(file.filename):
            continue
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:  # 20MB limit
            raise HTTPException(status_code=400, detail=f"Fichier trop volumineux: {file.filename}")
        
        saved_path = save_uploaded_file(content, file.filename, settings.pdf_dir)
        saved_paths.append(saved_path)
    
    if not saved_paths:
        raise HTTPException(status_code=400, detail="Aucun PDF valide")
    
    try:
        result = get_rag_service().ingest_pdfs(saved_paths)
        return PDFIngestResponse(**result)
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_chart(
    file: UploadFile = File(...),
    top_k: int = Form(5),
    style: str = Form("general")
):
    if not is_allowed_image(file.filename):
        raise HTTPException(status_code=400, detail="Format image non supporté. Utilisez JPG, PNG, WEBP")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image trop volumineuse (max 10MB)")
    
    # Save temp image
    temp_dir = settings.data_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4().hex}_{file.filename}"
    
    with open(temp_path, "wb") as f:
        f.write(content)
    
    try:
        analysis_service = get_analysis_service()
        # Validate style
        valid_styles = [s["key"] for s in list_styles()]
        if style not in valid_styles:
            style = "general"
        result = analysis_service.analyze(temp_path, top_k=top_k, style_key=style)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur analyse: {str(e)}")
    finally:
        if temp_path.exists():
            temp_path.unlink()

@app.delete("/api/knowledge/clear")
async def clear_knowledge():
    try:
        get_vector_store().clear()
        # Also clear pdfs
        for pdf_file in settings.pdf_dir.glob("*.pdf"):
            pdf_file.unlink()
        return {"success": True, "message": "Base de connaissances effacée"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/styles")
async def get_trading_styles():
    return {"styles": list_styles()}

@app.get("/api/examples")
async def get_examples():
    """Retourne des exemples de prompts / patterns"""
    return {
        "patterns": [
            "tête-épaules",
            "double top/bottom",
            "triangle ascendant/descendant",
            "drapeau / fanion",
            "biseau",
            "canal haussier/baissier",
            "support/résistance",
            "HLZ: BOS, CHOCH, OB, FVG, Liquidité"
        ],
        "tips": [
            "Uploadez vos PDFs de cours pour que l'IA utilise VOTRE méthode",
            "Pour HLZ: uploadez PDFs séparés par concept (BOS, CHOCH, OB, FVG, Liquidité, Premium/Discount)",
            "Utilisez des captures nettes avec bougies visibles",
            "Plus vos PDFs sont structurés (un concept = un chapitre), mieux c'est",
            "Sélectionnez le style HLZ dans le menu pour une analyse spécialisée",
            "L'analyse fonctionne même sans PDFs, mais sera plus précise avec"
        ],
        "hlz_guide": {
            "title": "Comment préparer tes PDFs HLZ Complet",
            "steps": [
                "1. Découpe ton cours HLZ en 6-8 PDFs thématiques: Structure (HH/HL), BOS/CHOCH, Order Blocks, FVG, Liquidités, Premium/Discount, Entry Models, Exemples",
                "2. Chaque PDF doit avoir: Définition claire, Règles de validation, 2-3 exemples graphiques décrits en texte, Erreurs à éviter",
                "3. Utilise des titres clairs: 'HLZ - Order Block - Définition et validation' pour que le RAG retrouve facilement",
                "4. Évite les PDFs scannés image-only, le texte doit être sélectionnable",
                "5. Bonus: Ajoute un PDF 'HLZ Checklist' avec checklist entrée/sortie que l'IA pourra citer"
            ]
        }
    }

# For HuggingFace Spaces compatibility
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
