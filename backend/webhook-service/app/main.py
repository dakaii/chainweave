from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="ChainWeave Webhook Service", version="0.1.0")


@app.post("/webhook/helius")
async def receive_helius_webhook(payload: Dict[str, Any]):
    # Minimal contract-compliant response acknowledging receipt
    return {
        "status": "received",
        "message_id": None,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0",
    }



