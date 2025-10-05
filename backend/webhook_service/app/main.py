from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
import re


app = FastAPI(title="ChainWeave Webhook Service", version="0.1.0")


_BASE58 = re.compile(r"^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$")


@app.post("/webhook/helius")
async def receive_helius_webhook(payload: Dict[str, Any]):
    # Basic validations per contract examples
    required_fields = ["type", "signature", "timestamp", "slot", "events"]
    for f in required_fields:
        if f not in payload:
            return JSONResponse(status_code=400, content={"error": "validation_failed", "message": f"Missing field: {f}", "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})

    if payload.get("type") not in ["ENHANCED", "RAW"]:
        return JSONResponse(status_code=400, content={"error": "validation_failed", "message": "Invalid type", "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})

    signature = payload.get("signature")
    if not isinstance(signature, str) or not (87 <= len(signature) <= 88) or not _BASE58.match(signature):
        return JSONResponse(status_code=400, content={"error": "validation_failed", "message": "Invalid signature", "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})

    events = payload.get("events")
    if not isinstance(events, dict):
        return JSONResponse(status_code=400, content={"error": "validation_failed", "message": "Invalid events", "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})

    nft = events.get("nft") or {}
    nft_mint: Optional[str] = nft.get("nftMint")
    if nft_mint is None or not isinstance(nft_mint, str) or not (32 <= len(nft_mint) <= 44) or not _BASE58.match(nft_mint):
        return JSONResponse(status_code=400, content={"error": "validation_failed", "message": "Invalid nftMint", "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})

    # Simulate successful enqueue/processing with a message_id
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "status": "received",
        "message_id": "projects/chainweave/topics/nft-events/messages/12345",
        "timestamp": ts,
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "version": "0.1.0",
    }


@app.head("/health")
async def health_head():
    # Return same status as GET with empty body
    return Response(status_code=200)


