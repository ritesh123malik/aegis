import math
from datetime import datetime
from typing import Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.models.outcome import Outcome
from backend.app.services.osm_service import get_cached_junctions

router = APIRouter(prefix="/similar_events", tags=["similar_events"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_corridor_centroid(corridor: str) -> Optional[Tuple[float, float]]:
    junctions = get_cached_junctions(corridor)
    if not junctions:
        return None
    lats = [j["lat"] for j in junctions if j.get("lat") is not None]
    lngs = [j["lng"] for j in junctions if j.get("lng") is not None]
    if not lats or not lngs:
        return None
    return sum(lats) / len(lats), sum(lngs) / len(lngs)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Radius of the earth in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    return R * c

@router.get("/{event_id}")
def get_similar_events(event_id: str, db: Session = Depends(get_db)):
    target_event = db.query(Event).filter(Event.event_id == event_id).first()
    if not target_event:
        raise HTTPException(status_code=404, detail="Target event not found")
        
    target_cause = target_event.event_cause or "others"
    target_corridor = target_event.corridor or "Non-corridor"
    target_dt = target_event.start_datetime or datetime.utcnow()
    target_hour = target_dt.hour
    
    target_centroid = get_corridor_centroid(target_corridor)
    
    # Query all other events
    all_events = db.query(Event).filter(Event.event_id != event_id).all()
    
    scored_events = []
    
    for ev in all_events:
        # 1. Cause similarity (weight 0.5)
        cause_sim = 1.0 if (ev.event_cause or "others") == target_cause else 0.0
        
        # 2. Corridor proximity similarity (weight 0.3)
        ev_corridor = ev.corridor or "Non-corridor"
        if ev_corridor == target_corridor:
            corridor_sim = 1.0
        else:
            ev_centroid = get_corridor_centroid(ev_corridor)
            if target_centroid and ev_centroid:
                dist = haversine_distance(
                    target_centroid[0], target_centroid[1],
                    ev_centroid[0], ev_centroid[1]
                )
                corridor_sim = max(0.0, 1.0 - dist / 15.0)
            else:
                corridor_sim = 0.0
                
        # 3. Time-of-day similarity (weight 0.2)
        ev_dt = ev.start_datetime or datetime.utcnow()
        ev_hour = ev_dt.hour
        hour_diff = abs(target_hour - ev_hour)
        circ_diff = min(hour_diff, 24.0 - hour_diff)
        time_sim = 1.0 - (circ_diff / 12.0)
        
        # Total similarity score
        similarity_score = 0.5 * cause_sim + 0.3 * corridor_sim + 0.2 * time_sim
        
        scored_events.append((ev, similarity_score))
        
    # Sort by similarity score descending
    scored_events.sort(key=lambda x: x[1], reverse=True)
    
    # Take top 5
    top_5 = scored_events[:5]
    
    result = []
    for ev, score in top_5:
        # Check outcome
        outcome = db.query(Outcome).filter(Outcome.event_id == ev.event_id).first()
        outcome_data = None
        if outcome:
            outcome_data = {
                "actual_duration_min": outcome.actual_duration_min,
                "actual_disruption_class": outcome.actual_disruption_class,
                "notes": outcome.notes
            }
            
        result.append({
            "event_id": ev.event_id,
            "event_type": ev.event_type,
            "event_cause": ev.event_cause,
            "corridor": ev.corridor,
            "start_datetime": ev.start_datetime.isoformat() if ev.start_datetime else None,
            "requires_road_closure": ev.requires_road_closure,
            "similarity_score": float(score),
            "outcome": outcome_data
        })
        
    return result
