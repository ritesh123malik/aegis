"""
Aegis — Prefetch OpenStreetMap Features Cache.

Queries Nominatim for corridor geocoding and fetches junctions, routes, and traffic
signals from Overpass, caching them locally to prevent live calls during the demo.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
import pandas as pd
import requests

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from backend.app.services.osm_service import (
    fetch_junctions_from_overpass,
    fetch_routes_from_overpass,
    fetch_signals_from_overpass,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PARQUET_PATH = PROJECT_ROOT / "data" / "processed" / "cleaned_events.parquet"
OUTPUT_CACHE_PATH = PROJECT_ROOT / "data" / "processed" / "osm_cache.json"

def clean_corridor_name(name: str) -> str:
    """
    Cleans raw corridor names to maximize geocoding success on Nominatim.
    """
    cleaned = name.strip()
    
    # Replace ORR with Outer Ring Road
    if "ORR" in cleaned:
        cleaned = cleaned.replace("ORR", "Outer Ring Road")
        
    # Strip trailing numbers (e.g. ORR East 2 -> Outer Ring Road East, Bellary Road 2 -> Bellary Road)
    parts = cleaned.split()
    if parts and parts[-1].isdigit():
        cleaned = " ".join(parts[:-1])
        
    # Specific overrides for Bengaluru-specific routes
    overrides = {
        "Airport New South Road": "Kempegowda International Airport Road",
        "CBD": "Mahatma Gandhi Road",  # CBD center around MG Road
        "West of Chord Road": "West of Chord Road",
        "IRR(Thanisandra road)": "Thanisandra Main Road",
        "IRR": "Inner Ring Road",
        "Bannerghata Road": "Bannerghatta Road",
    }
    
    for k, v in overrides.items():
        if k in cleaned:
            cleaned = v
            break
            
    return cleaned

def prefetch_osm_cache() -> None:
    logger.info(f"Reading unique corridors from {PARQUET_PATH}...")
    if not PARQUET_PATH.exists():
        logger.error(f"Cleaned events parquet not found at {PARQUET_PATH}. Run training pipeline first.")
        return

    df = pd.read_parquet(PARQUET_PATH)
    unique_corridors = df["corridor"].dropna().unique().tolist()
    logger.info(f"Found {len(unique_corridors)} unique corridors in dataset: {unique_corridors}")

    cache_data = {}
    geocoding_failures = []
    skipped_corridors = []

    nominatim_url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "Aegis-Hackathon-Project/1.0 (contact: ritesh123malik@github.com)"
    }

    for corridor in unique_corridors:
        if corridor == "Non-corridor":
            logger.info("Skipping 'Non-corridor' explicitly...")
            skipped_corridors.append(corridor)
            continue

        query_name = clean_corridor_name(corridor)
        logger.info(f"Geocoding corridor '{corridor}' as '{query_name}, Bengaluru'...")

        # Strict Nominatim usage policy compliance: sleep 1.2s between requests
        time.sleep(1.2)

        try:
            params = {
                "q": f"{query_name}, Bengaluru",
                "format": "json",
                "limit": 1
            }
            res = requests.get(nominatim_url, headers=headers, params=params, timeout=15)
            res.raise_for_status()
            results = res.json()

            if not results:
                logger.warning(f"Nominatim returned no results for '{query_name}, Bengaluru'.")
                geocoding_failures.append(corridor)
                continue

            bbox_raw = results[0].get("boundingbox")
            if not bbox_raw or len(bbox_raw) < 4:
                logger.warning(f"Invalid bounding box returned for '{query_name}'.")
                geocoding_failures.append(corridor)
                continue

            # Parse bbox: [minlat, maxlat, minlon, maxlon]
            # Add a small buffer buffer (~200m) to expand search area slightly
            min_lat = float(bbox_raw[0]) - 0.002
            max_lat = float(bbox_raw[1]) + 0.002
            min_lon = float(bbox_raw[2]) - 0.002
            max_lon = float(bbox_raw[3]) + 0.002
            corridor_bbox = (min_lat, min_lon, max_lat, max_lon)

            logger.info(f"Successfully geocoded '{corridor}'. BBox: {corridor_bbox}")

            logger.info(f"Fetching features for '{corridor}' from Overpass...")
            junctions = fetch_junctions_from_overpass(corridor_bbox)
            routes = fetch_routes_from_overpass(corridor_bbox)
            signals = fetch_signals_from_overpass(corridor_bbox)

            logger.info(f"Retrieved: {len(junctions)} junctions, {len(routes)} routes, {len(signals)} signals.")

            cache_data[corridor] = {
                "junctions": junctions,
                "routes": routes,
                "signals": signals
            }

        except Exception as e:
            logger.error(f"Exception raised while processing corridor '{corridor}': {e}")
            geocoding_failures.append(corridor)

    # Save to JSON
    OUTPUT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)

    logger.info("\n" + "="*80)
    logger.info("PREFETCH WORK COMPLETE")
    logger.info(f"Saved cache file to: {OUTPUT_CACHE_PATH}")
    logger.info(f"Successfully processed: {len(cache_data)} corridors")
    logger.info(f"Skipped: {len(skipped_corridors)} ('Non-corridor')")
    logger.info(f"Failed to geocode: {len(geocoding_failures)}")
    if geocoding_failures:
        logger.info(f"Failed list: {geocoding_failures}")
    logger.info("="*80 + "\n")

if __name__ == "__main__":
    prefetch_osm_cache()
