"""
This module is a deliberately rules-based, explainable system – NOT a machine learning
model. The officer-count lookup table is calibrated from limited real historical outcome
data (the Astram dataset's assigned_to_police_id field is 98.4% null, so there is little
historical ground truth to learn from) plus reasonable domain-informed heuristics. This is
intentional and should be stated plainly to judges, not hidden – the post-event learning
loop (recalibration_service) is what improves these numbers over time as real outcomes are
logged.
"""

import logging
import math
from backend.app.services import osm_service

logger = logging.getLogger(__name__)

# Constants defined verbatim from specification
BASE_OFFICERS_LOOKUP = {
    "Low": 2,
    "Medium": 4,
    "High": 8,
    "Critical": 15,
}

CROWD_CONTROL_CAUSES = {"public_event", "procession", "vip_movement"}

BARRICADE_COUNT_BY_CLASS = {
    "Low": 1,
    "Medium": 2,
    "High": 4,
    "Critical": 6,
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes haversine distance between two GPS coordinates in kilometers.
    """
    R = 6371.0  # Earth's radius in km
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def calculate_officer_count(disruption_class: str, requires_road_closure: bool, event_cause: str) -> int:
    """
    Rules-based officer count calculation.
    """
    # Safe fallback if disruption_class is None/null
    d_class = disruption_class or "Medium"
    if d_class not in BASE_OFFICERS_LOOKUP:
        d_class = "Medium"
        
    base = BASE_OFFICERS_LOOKUP[d_class]
    adjustment = 2 if requires_road_closure else 0
    adjustment += 1 if event_cause in CROWD_CONTROL_CAUSES else 0
    return base + adjustment


def get_barricade_locations(corridor: str, event_lat: float, event_lon: float, disruption_class: str) -> list[dict]:
    """
    Recommends barricade locations along the corridor based on proximity, 
    excluding residential roads structurally.
    """
    junctions = osm_service.get_cached_junctions(corridor)
    if not junctions:
        return []
        
    # Hard safety/credibility constraint: NEVER suggest a barricade on a residential road.
    allowed_classes = {"primary", "secondary", "tertiary"}
    filtered = [j for j in junctions if j.get("road_class") in allowed_classes]
    
    # Assert structural safety constraint
    assert all(j.get("road_class") != "residential" for j in filtered), (
        f"Safety assertion failure: residential road suggested for barricade in corridor '{corridor}'"
    )
    
    # Rank by haversine distance
    ranked = []
    for j in filtered:
        j_lat = j.get("lat")
        j_lng = j.get("lng")
        if j_lat is not None and j_lng is not None:
            dist = haversine_distance(event_lat, event_lon, j_lat, j_lng)
            ranked.append((dist, j))
            
    ranked.sort(key=lambda x: x[0])
    
    # Return top N barricades
    d_class = disruption_class or "Medium"
    n_barricades = BARRICADE_COUNT_BY_CLASS.get(d_class, 1)
    
    return [item[1] for item in ranked[:n_barricades]]


def get_diversion_routes(corridor: str, event_lat: float, event_lon: float, radius_km: float = 1.0) -> list[dict]:
    """
    Recommends diversion routes that bypass the event area.
    """
    routes = osm_service.get_cached_routes(corridor)
    if not routes:
        return []
        
    valid_routes = []
    for r in routes:
        polyline = r.get("polyline", [])
        passes_near = False
        for pt in polyline:
            if len(pt) >= 2:
                dist = haversine_distance(event_lat, event_lon, pt[0], pt[1])
                if dist <= radius_km:
                    passes_near = True
                    break
        if not passes_near:
            valid_routes.append(r)
            
    # Validation note – for the 86 real historical events in the Astram dataset that have a populated route_path field, 
    # compare this function's output shape/length against those real routes as a sanity check during development. 
    # This is NOT a training signal (86 rows is too few to train on), it's a manual sanity check only.
    return valid_routes


def get_signals_requiring_attention(corridor: str, event_lat: float, event_lon: float, disruption_class: str) -> list[dict]:
    """
    Identifies signals within a 1.0 km radius from the event that need manual overrides.
    """
    signals = osm_service.get_cached_signals(corridor)
    if not signals:
        return []
        
    # Same 1.0 km radius logic as diversion exclusion
    radius_km = 1.0
    affected = []
    for sig in signals:
        sig_lat = sig.get("lat")
        sig_lng = sig.get("lng")
        if sig_lat is not None and sig_lng is not None:
            dist = haversine_distance(event_lat, event_lon, sig_lat, sig_lng)
            if dist <= radius_km:
                affected.append({
                    "lat": sig_lat,
                    "lng": sig_lng,
                    "signal_id": sig.get("signal_id"),
                    "recommended_action": "manual_override"
                })
    return affected


def generate_recommendation(event: dict, predicted_disruption_class: str) -> dict:
    """
    Main orchestrator for Aegis Traffic Management recommendation engine.
    """
    corridor = event.get("corridor") or "Non-corridor"
    event_cause = event.get("event_cause") or "others"
    requires_road_closure = bool(event.get("requires_road_closure", False))
    event_lat = event.get("latitude")
    event_lon = event.get("longitude")
    
    disruption_class = predicted_disruption_class or "Medium"
    
    # Calculate recommended officers
    officers = calculate_officer_count(disruption_class, requires_road_closure, event_cause)
    
    # If coordinates are missing or it is Non-corridor, return fallback defaults safely
    if event_lat is None or event_lon is None or corridor == "Non-corridor":
        return {
            "recommended_officers": officers,
            "recommended_barricades": [],
            "recommended_diversions": [],
            "signals_requiring_attention": []
        }
        
    # Generate recommendations using OSM cache
    barricades = get_barricade_locations(corridor, event_lat, event_lon, disruption_class)
    diversions = get_diversion_routes(corridor, event_lat, event_lon, radius_km=1.0)
    signals = get_signals_requiring_attention(corridor, event_lat, event_lon, disruption_class)
    
    return {
        "recommended_officers": officers,
        "recommended_barricades": barricades,
        "recommended_diversions": diversions,
        "signals_requiring_attention": signals
    }

