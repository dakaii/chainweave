from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse


app = FastAPI(title="ChainWeave Dashboard API", version="0.1.0")


# Error response shape per contracts/ErrorResponse
def error_response(error: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.get("/collections")
def list_collections(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("total_volume"),
    order: str = Query("desc"),
):
    valid_sort = {"total_volume", "floor_price", "created_at", "holder_count"}
    if sort_by not in valid_sort:
        return error_response("validation_failed", "Invalid sort_by parameter", 400)

    if order not in {"asc", "desc"}:
        return error_response("validation_failed", "Invalid order parameter", 400)

    collections: List[Dict[str, Any]] = []
    total_count = 0
    has_next = (offset + limit) < total_count

    return {
        "collections": collections,
        "total_count": total_count,
        "pagination": {"limit": limit, "offset": offset, "has_next": has_next},
    }


@app.get("/collections/{collection_id}")
def get_collection_details(
    collection_id: str = Path(..., min_length=1, max_length=200),
):
    # Minimal mock: no data yet → return 404 using contract error shape
    return error_response("not_found", "Collection not found", 404)


@app.get("/collections/{collection_id}/heatmap")
def get_collection_heatmap(collection_id: str = Path(..., min_length=1, max_length=200)):
    # Return an empty but valid heatmap payload per contract
    return {
        "collection_id": collection_id,
        "nfts": [],
        "color_scale": {"min_hold_days": 0, "max_hold_days": 0, "color_mapping": {}},
    }


@app.get("/whales")
def list_whales(
    limit: int = Query(20, ge=1, le=50),
    activity_days: int = Query(7, ge=1, le=90),
):
    return {
        "whales": [],
        "activity_period_days": activity_days,
        "total_count": 0,
    }


@app.get("/wallets/{wallet_address}")
def get_wallet_profile(wallet_address: str = Path(..., min_length=32, max_length=50)):
    return error_response("not_found", "Wallet not found", 404)


@app.post("/attributes/analysis")
def analyze_attributes(payload: Dict[str, Any]):
    # Validate minimal required field
    collection_ids: Optional[List[str]] = payload.get("collection_ids") if isinstance(payload, dict) else None
    if not collection_ids or not isinstance(collection_ids, list):
        return error_response("validation_failed", "collection_ids is required", 400)

    return {
        "analysis_date": datetime.now().isoformat(),
        "collections": [],
    }



