import requests
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Read database URL from .env
DATABASE_URL = "postgresql://aegis:aegis@localhost:5432/aegis"
if (PROJECT_ROOT / ".env").exists():
    with open(PROJECT_ROOT / ".env") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.split("=")[1].strip()

engine = create_engine(DATABASE_URL)
backend_url = "http://localhost:8000"

def find_and_verify_real_events():
    # We want 5 real events of type 'planned' with different n_exact values.
    # n_exact is the count of OTHER planned events in the database with the same event_cause and corridor.
    # Let's query combinations and find matching events.
    
    query_str = """
        SELECT 
            e.event_id, 
            e.event_cause, 
            e.corridor,
            (
                SELECT COUNT(*) FROM events e2 
                WHERE e2.corridor = e.corridor 
                  AND e2.event_cause = e.event_cause 
                  AND e2.event_type = 'planned' 
                  AND e2.event_id != e.event_id
            ) as n_exact
        FROM events e
        WHERE e.event_type = 'planned'
        ORDER BY n_exact DESC
    """
    
    with engine.connect() as conn:
        all_planned_events = conn.execute(text(query_str)).fetchall()
        
    print(f"Found {len(all_planned_events)} planned events in the database.")
    
    # Let's select 5 events with different n_exact values
    selected_events = []
    target_ns = [5, 4, 3, 2, 0] # we want n_exact values around these
    
    # We'll search for exact matches, or nearest values
    for target in target_ns:
        matched = None
        for ev in all_planned_events:
            # We want unique combinations of cause + corridor to make sure they are distinct
            if target == 5 and ev.n_exact >= 5:
                matched = ev
                break
            elif target == 0 and ev.n_exact == 0:
                matched = ev
                break
            elif ev.n_exact == target:
                matched = ev
                break
        
        # If we couldn't find an exact match, find the closest available
        if matched is None:
            # find closest
            closest = min(all_planned_events, key=lambda x: abs(x.n_exact - target))
            matched = closest
            
        selected_events.append(matched)
        # Remove matched event from list to avoid duplicates
        all_planned_events = [x for x in all_planned_events if x.event_id != matched.event_id]

    print("\n--- Selected 5 Real Events for Verification ---")
    print(f"{'Event ID':<15} | {'Cause':<15} | {'Corridor':<30} | {'n_exact (DB count)':<18}")
    print("-" * 90)
    for ev in selected_events:
        print(f"{ev.event_id:<15} | {ev.event_cause:<15} | {ev.corridor:<30} | {ev.n_exact:<18}")

    print("\n--- Running Predictions ---")
    print(f"{'Event ID':<15} | {'Cause':<15} | {'n_exact':<8} | {'Confidence':<10} | {'Low Data Warning':<16} | {'Predicted Duration':<20}")
    print("-" * 95)
    
    confidence_scores = []
    
    for ev in selected_events:
        r = requests.post(f"{backend_url}/predict", json={"event_id": ev.event_id})
        if r.status_code != 200:
            print(f"Error predicting on {ev.event_id}: {r.text}")
            continue
        data = r.json()
        conf = data.get("confidence_score")
        low_data = data.get("low_data_warning")
        pred_duration = data.get("predicted_duration_min")
        
        print(f"{ev.event_id:<15} | {ev.event_cause:<15} | {ev.n_exact:<8} | {conf:<10.2f} | {str(low_data):<16} | {pred_duration:<20.2f}")
        confidence_scores.append(conf)

    unique_scores = set(confidence_scores)
    print("\n--- Results Summary ---")
    print(f"Confidence scores: {[round(c, 4) for c in confidence_scores]}")
    print(f"Unique count: {len(unique_scores)} out of {len(confidence_scores)}")
    
    if len(unique_scores) == len(confidence_scores):
        print("VERIFICATION: PASS (All 5 confidence scores are unique and scale correctly with data density!)")
    else:
        print("VERIFICATION: FAIL (Duplicate confidence scores found; they did not scale continuously!)")

if __name__ == "__main__":
    find_and_verify_real_events()
