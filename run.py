#!/usr/bin/env python3
"""
Entry point local
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"""
╔════════════════════════════════════════════╗
║  TradingGraph AI - RAG + Vision            ║
║  {settings.app_name} v{settings.version}                 ║
║                                            ║
║  Docs: http://localhost:{settings.port}/docs          ║
║  App:  http://localhost:{settings.port}/              ║
╚════════════════════════════════════════════╝
    """)
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
