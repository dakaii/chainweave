from datetime import datetime
from typing import Any, Dict, List, Optional
import re

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse


app = FastAPI(title="ChainWeave Dashboard API", version="0.1.0")


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
    limit: Optional[str] = Query("20"),
    offset: Optional[str] = Query("0"),
    sort_by: str = Query("total_volume"),
    order: str = Query("desc"),
):
    valid_sort = {"total_volume", "floor_price", "created_at", "holder_count"}
    if sort_by not in valid_sort:
        return error_response("validation_failed", "Invalid sort_by parameter", 400)

    if order not in {"asc", "desc"}:
        return error_response("validation_failed", "Invalid order parameter", 400)

    # Manual numeric validation to return 400 (not 422)
    try:
        limit_int = int(limit) if isinstance(limit, str) else 20
        offset_int = int(offset) if isinstance(offset, str) else 0
    except ValueError:
        return error_response("validation_failed", "limit/offset must be integers", 400)

    if not (1 <= limit_int <= 100):
        return error_response("validation_failed", "limit out of range", 400)
    if offset_int < 0:
        return error_response("validation_failed", "offset must be >= 0", 400)

    collections: List[Dict[str, Any]] = []
    total_count = 0
    has_next = (offset_int + limit_int) < total_count

    return {
        "collections": collections,
        "total_count": total_count,
        "pagination": {"limit": limit_int, "offset": offset_int, "has_next": has_next},
    }


# Explicitly handle trailing slash to avoid interpreting it as a details request with empty ID
@app.get("/collections/")
def list_collections_trailing_slash():
    return error_response("not_found", "Not found", 404)


def _invalid_collection_id(cid: str) -> bool:
    if cid is None:
        return True
    if len(cid.strip()) == 0:
        return True
    if len(cid) > 256:
        return True
    if ".." in cid or "/" in cid or "\\" in cid or "%00" in cid:
        return True
    return False


@app.get("/collections/{collection_id}")
def get_collection_details(collection_id: str = Path(...)):
    if _invalid_collection_id(collection_id):
        return error_response("validation_failed", "invalid collection_id", 400)
    return error_response("not_found", "Collection not found", 404)


@app.get("/collections/{collection_id}/heatmap")
def get_collection_heatmap(collection_id: str = Path(...)):
    if _invalid_collection_id(collection_id):
        return error_response("validation_failed", "invalid collection_id", 400)
    # No data available → 404 per contract expectations
    return error_response("not_found", "Collection not found", 404)


@app.get("/whales")
def list_whales(
    limit: Optional[str] = Query("20"),
    activity_days: Optional[str] = Query("7"),
):
    try:
        limit_int = int(limit) if isinstance(limit, str) else 20
        days_int = int(activity_days) if isinstance(activity_days, str) else 7
    except ValueError:
        return error_response("validation_failed", "invalid numeric parameters", 400)
    if not (1 <= limit_int <= 50):
        return error_response("validation_failed", "limit out of range", 400)
    if not (1 <= days_int <= 90):
        return error_response("validation_failed", "activity_days out of range", 400)
    return {
        "whales": [],
        "activity_period_days": days_int,
        "total_count": 0,
    }


_BASE58 = re.compile(r"^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$")


@app.get("/wallets/{wallet_address}")
def get_wallet_profile(wallet_address: str = Path(...)):
    # Validate Solana address format (base58, 43-44 length typical in contract)
    if not isinstance(wallet_address, str) or not (32 <= len(wallet_address) <= 50) or not _BASE58.match(wallet_address):
        return error_response("validation_failed", "invalid wallet address", 400)
    return error_response("not_found", "Wallet not found", 404)


@app.post("/attributes/analysis")
def analyze_attributes(payload: Dict[str, Any]):
    collection_ids: Optional[List[str]] = payload.get("collection_ids") if isinstance(payload, dict) else None
    time_range_days: Optional[int] = payload.get("time_range_days") if isinstance(payload, dict) else None
    if not collection_ids or not isinstance(collection_ids, list):
        return error_response("validation_failed", "collection_ids is required", 400)
    if len(collection_ids) > 5:
        return error_response("validation_failed", "too many collection_ids", 400)
    if time_range_days is not None:
        try:
            tr = int(time_range_days)
        except Exception:
            return error_response("validation_failed", "invalid time_range_days", 400)
        if not (7 <= tr <= 365):
            return error_response("validation_failed", "time_range_days out of range", 400)

    return {
        "analysis_date": datetime.now().isoformat(),
        "collections": [],
    }


