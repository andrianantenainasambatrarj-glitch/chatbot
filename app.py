"""
HuggingFace Spaces entry point
HF expects app.py with app variable or gradio
We expose FastAPI app as `app`
"""
from app.main import app

# For HF Spaces Docker, ensure port 7860
if __name__ == "__main__":
    import uvicorn, os
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
