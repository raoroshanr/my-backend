"""
DeepSeeGoa - GHSL Explorer backend.

Serves Google Earth Engine tile URLs for a small set of JRC GHSL layers.
"""

import base64
import json
import logging
import os
import time
from enum import Enum
from typing import Optional

import ee
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deepseegoa")

# --------------------------------------------------------------------------
# Earth Engine initialization
# --------------------------------------------------------------------------
# Expects a base64-encoded service account JSON key in GEE_SERVICE_ACCOUNT_KEY.
# This is the standard way to authenticate a headless Cloud Run service:
#   base64 -w0 service-account.json  ->  set as the env var / secret
GEE_STATUS = "Not initialized"


def initialize_earth_engine() -> str:
    global GEE_STATUS
    try:
        raw_key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
        if not raw_key:
            raise RuntimeError("GEE_SERVICE_ACCOUNT_KEY environment variable is not set")

        key_dict = json.loads(base64.b64decode(raw_key))
        credentials = ee.ServiceAccountCredentials(
            key_dict["client_email"], key_data=json.dumps(key_dict)
        )
        ee.Initialize(credentials, project=key_dict.get("project_id"))
        GEE_STATUS = "Success"
        logger.info("Earth Engine initialized successfully")
    except Exception as exc:  # noqa: BLE001
        GEE_STATUS = f"Failed: {exc}"
        logger.exception("Earth Engine initialization failed")
    return GEE_STATUS


initialize_earth_engine()

# --------------------------------------------------------------------------
# Dataset registry — single source of truth for both the backend logic and
# whatever the frontend wants to show as a legend / dropdown.
# --------------------------------------------------------------------------
YEARS_1975_2030 = [str(y) for y in range(1975, 2031, 5)]

DATASETS = {
    "POP": {
        "label": "Population",
        "kind": "collection",
        "asset_id": "JRC/GHSL/P2023A/GHS_POP",
        "band": "population_count",
        "years": YEARS_1975_2030,
        "vis": {
            "min": 0.0,
            "max": 100.0,
            "palette": ["000004", "320a5a", "781b6c", "bb3654", "ec6824", "fbb41a", "fcffa4"],
        },
        "unit": "people / 100m cell",
    },
    "BUILT_S": {
        "label": "Built-Up Surface",
        "kind": "collection",
        "asset_id": "JRC/GHSL/P2023A/GHS_BUILT_S",
        "band": "built_surface",
        "years": YEARS_1975_2030,
        "vis": {"min": 0.0, "max": 8000.0, "palette": ["000000", "ffffff"]},
        "unit": "m² / 100m cell",
    },
    "BUILT_V": {
        "label": "Building Volume (3D)",
        "kind": "collection",
        "asset_id": "JRC/GHSL/P2023A/GHS_BUILT_V",
        "band": "built_volume_total",
        "years": YEARS_1975_2030,
        "vis": {
            "min": 0.0,
            "max": 80000.0,
            "palette": ["000004", "51127c", "b73779", "fc8961", "fcfdbf"],
        },
        "unit": "m³ / 100m cell",
    },
    "SMOD": {
        "label": "Urbanization Model",
        "kind": "collection",
        # NOTE: the old "GHS_SMOD" asset was retired by JRC and is no longer
        # queryable in Earth Engine. The replacement is GHS_SMOD_V2-0.
        "asset_id": "JRC/GHSL/P2023A/GHS_SMOD_V2-0",
        "band": "smod_code",
        "years": YEARS_1975_2030,
        "vis": {"min": 11.0, "max": 30.0, "palette": ["0000aa", "004400", "ffff00", "ff0000"]},
        "unit": "degree-of-urbanisation class",
    },
    "BUILT_H": {
        "label": "Building Height",
        "kind": "image",
        "asset_id": "JRC/GHSL/P2023A/GHS_BUILT_H/2018",
        "band": "built_height",
        "years": ["2018"],
        "vis": {
            "min": 0.0,
            "max": 20.0,
            "palette": ["000000", "0d0887", "7e03a8", "cc4778", "f89540", "f0f921"],
        },
        "unit": "avg. height (m)",
    },
    "OBAT": {
        "label": "OBAT Building Footprints",
        "kind": "vector",
        "asset_id": "projects/sat-io/open-datasets/ghs-obat",
        "years": ["Latest Available"],
        "vis": {},
        "unit": "building footprint",
    },
}

ProductId = Enum("ProductId", {k: k for k in DATASETS}, type=str)

# --------------------------------------------------------------------------
# Very small in-memory cache for tile URLs. GEE map tokens are valid for a
# while but not forever, so entries expire rather than being cached forever.
# --------------------------------------------------------------------------
_TILE_CACHE: dict[str, tuple[str, float]] = {}
_TILE_CACHE_TTL_SECONDS = 55 * 60  # keep comfortably under GEE token lifetime


def _cache_get(key: str) -> Optional[str]:
    entry = _TILE_CACHE.get(key)
    if not entry:
        return None
    tile_url, created_at = entry
    if time.time() - created_at > _TILE_CACHE_TTL_SECONDS:
        _TILE_CACHE.pop(key, None)
        return None
    return tile_url


def _cache_set(key: str, tile_url: str) -> None:
    _TILE_CACHE[key] = (tile_url, time.time())


# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------
app = FastAPI(title="DeepSeeGoa GHSL Explorer API")

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins.split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "earth_engine": GEE_STATUS}


@app.get("/api/products")
def list_products():
    """Lets the frontend build its dropdowns/legend from the same source of truth as the backend."""
    return {
        key: {
            "label": cfg["label"],
            "years": cfg["years"],
            "vis": cfg["vis"],
            "unit": cfg["unit"],
        }
        for key, cfg in DATASETS.items()
    }


def _build_layer(product: str, epoch: str):
    """Returns an ee.Image (already band-selected) for the requested product/epoch."""
    cfg = DATASETS[product]

    if cfg["kind"] == "collection":
        collection = ee.ImageCollection(cfg["asset_id"])
        image = collection.filterDate(f"{epoch}-01-01", f"{epoch}-12-31").first()
        image = ee.Image(image).select(cfg["band"])
        return image, cfg["vis"]

    if cfg["kind"] == "image":
        image = ee.Image(cfg["asset_id"]).select(cfg["band"])
        return image, cfg["vis"]

    if cfg["kind"] == "vector":
        vector = ee.FeatureCollection(cfg["asset_id"])
        image = vector.style(color="000055", width=1, fillColor="00ffff")
        return image, {}

    raise ValueError(f"Unhandled dataset kind for product {product}")


@app.get("/api/map-tiles")
def get_map_tiles(
    product: ProductId = Query(...),
    epoch: str = Query("2020"),
):
    if GEE_STATUS != "Success":
        raise HTTPException(status_code=503, detail=f"Earth Engine unavailable: {GEE_STATUS}")

    product_key = product.value
    cfg = DATASETS[product_key]
    if epoch not in cfg["years"]:
        raise HTTPException(
            status_code=400,
            detail=f"'{epoch}' is not a valid epoch for {product_key}. Valid: {cfg['years']}",
        )

    cache_key = f"{product_key}:{epoch}"
    cached = _cache_get(cache_key)
    if cached:
        return {"tile_url": cached, "cached": True}

    try:
        image, vis_params = _build_layer(product_key, epoch)
        map_id_dict = image.getMapId(vis_params)
        tile_url = map_id_dict["tile_fetcher"].url_format
        _cache_set(cache_key, tile_url)
        return {"tile_url": tile_url, "cached": False}

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to build map tiles for %s", cache_key)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
