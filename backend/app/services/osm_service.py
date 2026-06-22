# OpenStreetMap integration for road network and routing data.
import json
import logging
from pathlib import Path
import requests
import time

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # aegis root
CACHE_FILE_PATH = PROJECT_ROOT / "data" / "processed" / "osm_cache.json"

# Load the cache once at module import time
_cache = {}
if CACHE_FILE_PATH.exists():
    try:
        with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        logger.info(f"Loaded OSM cache from {CACHE_FILE_PATH} containing {len(_cache)} corridors.")
    except Exception as e:
        logger.warning(f"Failed to load OSM cache from {CACHE_FILE_PATH}: {e}")
else:
    logger.warning(f"OSM cache file not found at {CACHE_FILE_PATH}. Cached reads will return empty.")


# ==============================================================================
# 1. Cached Read Functions (Runtime/Demo Mode — NEVER make network calls)
# ==============================================================================

def get_cached_junctions(corridor: str) -> list[dict]:
    """
    Get cached junctions for the given corridor.
    Returns: list of {lat, lng, junction_name, road_class} dicts
    """
    if corridor not in _cache:
        logger.warning(f"Corridor '{corridor}' not found in OSM cache.")
        return []
    return _cache[corridor].get("junctions", [])


def get_cached_routes(corridor: str) -> list[dict]:
    """
    Get cached routes for the given corridor.
    Returns: list of {polyline: [[lat, lng], ...], description} dicts
    """
    if corridor not in _cache:
        logger.warning(f"Corridor '{corridor}' not found in OSM cache.")
        return []
    return _cache[corridor].get("routes", [])


def get_cached_signals(corridor: str) -> list[dict]:
    """
    Get cached traffic signals for the given corridor.
    Returns: list of {lat, lng, signal_id} dicts
    """
    if corridor not in _cache:
        logger.warning(f"Corridor '{corridor}' not found in OSM cache.")
        return []
    return _cache[corridor].get("signals", [])


# ==============================================================================
# 2. Live Fetch Functions (Development/Data Prep Mode Only)
# ==============================================================================

def fetch_junctions_from_overpass(corridor_bbox: tuple) -> list[dict]:
    """
    Queries the Overpass API for junctions (ways) within a bounding box.
    corridor_bbox: (min_lat, min_lon, max_lat, max_lon)
    """
    min_lat, min_lon, max_lat, max_lon = corridor_bbox
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    way["highway"~"^(primary|secondary|tertiary|residential)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    out center;
    """
    
    for attempt in range(3):
        try:
            headers = {
                "User-Agent": "Aegis-Hackathon-Project/1.0 (contact: ritesh123malik@github.com)",
                "Accept": "application/json"
            }
            res = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=60)
            if res.status_code == 200:
                data = res.json()
                junctions = []
                for element in data.get("elements", []):
                    tags = element.get("tags", {})
                    center = element.get("center", {})
                    junctions.append({
                        "lat": center.get("lat"),
                        "lng": center.get("lon"),
                        "junction_name": tags.get("name", f"Junction {element.get('id')}"),
                        "road_class": tags.get("highway")
                    })
                return junctions
            elif res.status_code in [429, 504]:
                if attempt < 2:
                    logger.warning(f"Overpass returned status {res.status_code}. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
            res.raise_for_status()
        except Exception as e:
            if attempt < 2:
                logger.warning(f"Overpass call failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            logger.error(f"Failed to fetch junctions from Overpass: {e}")
            raise
    return []


def fetch_routes_from_overpass(corridor_bbox: tuple) -> list[dict]:
    """
    Queries the Overpass API for way geometries along major roads in the bbox.
    """
    min_lat, min_lon, max_lat, max_lon = corridor_bbox
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    out geom;
    """
    
    for attempt in range(3):
        try:
            headers = {
                "User-Agent": "Aegis-Hackathon-Project/1.0 (contact: ritesh123malik@github.com)",
                "Accept": "application/json"
            }
            res = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=60)
            if res.status_code == 200:
                data = res.json()
                routes = []
                for element in data.get("elements", []):
                    tags = element.get("tags", {})
                    geometry = element.get("geometry", [])
                    polyline = [[pt.get("lat"), pt.get("lon")] for pt in geometry]
                    if polyline:
                        routes.append({
                            "polyline": polyline,
                            "description": tags.get("name", f"Road {element.get('id')}")
                        })
                return routes
            elif res.status_code in [429, 504]:
                if attempt < 2:
                    logger.warning(f"Overpass returned status {res.status_code}. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
            res.raise_for_status()
        except Exception as e:
            if attempt < 2:
                logger.warning(f"Overpass call failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            logger.error(f"Failed to fetch routes from Overpass: {e}")
            raise
    return []


def fetch_signals_from_overpass(corridor_bbox: tuple) -> list[dict]:
    """
    Queries the Overpass API for highway=traffic_signals nodes.
    """
    min_lat, min_lon, max_lat, max_lon = corridor_bbox
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    node["highway"="traffic_signals"]({min_lat},{min_lon},{max_lat},{max_lon});
    out body;
    """
    
    for attempt in range(3):
        try:
            headers = {
                "User-Agent": "Aegis-Hackathon-Project/1.0 (contact: ritesh123malik@github.com)",
                "Accept": "application/json"
            }
            res = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=60)
            if res.status_code == 200:
                data = res.json()
                signals = []
                for element in data.get("elements", []):
                    signals.append({
                        "lat": element.get("lat"),
                        "lng": element.get("lon"),
                        "signal_id": str(element.get("id"))
                    })
                return signals
            elif res.status_code in [429, 504]:
                if attempt < 2:
                    logger.warning(f"Overpass returned status {res.status_code}. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
            res.raise_for_status()
        except Exception as e:
            if attempt < 2:
                logger.warning(f"Overpass call failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            logger.error(f"Failed to fetch signals from Overpass: {e}")
            raise
    return []
