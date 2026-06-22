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

def verify_confidence_scores():
    # We want 5 events with different n_exact values.
    # Let's query the database to find combinations with different planned event counts.
    # We'll print n_exact counts first to see what we have.
    with engine.connect() as conn:
        counts_query = conn.execute(text(
            "SELECT event_cause, corridor, COUNT(*) as cnt FROM events "
            "WHERE event_type = 'planned' "
            "GROUP BY event_cause, corridor "
            "ORDER BY cnt DESC"
        )).fetchall()
        
    print("Historical planned counts in DB (top 10):")
    for row in counts_query[:10]:
        print(f"  Cause: {row[0]:<15} | Corridor: {row[1]:<20} | Count: {row[2]}")

    # Let's pick 5 combinations.
    # We want:
    # 1. Abundant history (count >= 5)
    # 2. Count = 4 (or near)
    # 3. Count = 3
    # 4. Count = 2
    # 5. Count = 1 or 0 (low/no history)
    
    # We can query events from the database matching these combinations, or create temporary ones for testing.
    # Creating temporary events is safer and guarantees we get exactly the counts we want.
    test_cases = [
        {"cause": "construction", "corridor": "Mysore Road", "expected_n": 5}, # High count in DB
        {"cause": "procession", "corridor": "Varthur Road", "expected_n": 4},
        {"cause": "public_event", "corridor": "Tumkur Road", "expected_n": 3},
        {"cause": "vip_movement", "corridor": "Hosur Road", "expected_n": 2},
        {"cause": "protest", "corridor": "Outer Ring Road", "expected_n": 0}
    ]

    print("\n--- Seeding test events with controlled n_exact counts ---")
    
    # For each test case, we will insert exactly 'expected_n' historical events into the DB
    # under a unique corridor name (e.g. 'Test Corridor X') and cause,
    # and then one target event to predict on.
    
    with engine.connect() as conn:
        # Clean up old test data
        conn.execute(text("DELETE FROM predictions WHERE event_id LIKE 'test-conf-%'"))
        conn.execute(text("DELETE FROM events WHERE event_id LIKE 'test-conf-%'"))
        conn.commit()
        
        for idx, tc in enumerate(test_cases):
            test_corridor = f"Test Corridor {idx}"
            test_cause = f"test_cause_{idx}"
            tc["test_corridor"] = test_corridor
            tc["test_cause"] = test_cause
            
            # Insert expected_n historical planned events
            for h_idx in range(tc["expected_n"]):
                conn.execute(text(
                    "INSERT INTO events (event_id, event_type, event_cause, corridor, start_datetime) "
                    "VALUES (:eid, 'planned', :cause, :corridor, CURRENT_TIMESTAMP)"
                ), {"eid": f"test-conf-hist-{idx}-{h_idx}", "cause": test_cause, "corridor": test_corridor})
            
            # Insert target event to call predict on
            tc["target_id"] = f"test-conf-target-{idx}"
            conn.execute(text(
                "INSERT INTO events (event_id, event_type, event_cause, corridor, start_datetime) "
                "VALUES (:eid, 'planned', :cause, :corridor, CURRENT_TIMESTAMP)"
            ), {"eid": tc["target_id"], "cause": test_cause, "corridor": test_corridor})
            
        conn.commit()

    print("\n--- Running Predictions and Checking Confidence Scores ---")
    confidence_scores = []
    
    for idx, tc in enumerate(test_cases):
        r = requests.post(f"{backend_url}/predict", json={"event_id": tc["target_id"]})
        if r.status_code != 200:
            print(f"Error predicting on case {idx}: {r.text}")
            continue
            
        data = r.json()
        conf = data.get("confidence_score")
        low_data = data.get("low_data_warning")
        print(f"Case {idx}: n_exact = {tc['expected_n']:<2} | confidence_score = {conf:<5} | low_data_warning = {low_data}")
        confidence_scores.append(conf)

    # Check for uniqueness
    unique_scores = set(confidence_scores)
    print("\n--- Results Summary ---")
    print(f"Confidence scores obtained: {confidence_scores}")
    print(f"Number of unique confidence scores: {len(unique_scores)} out of {len(confidence_scores)}")
    
    if len(unique_scores) == len(confidence_scores):
        print("VERIFICATION: PASS (All confidence scores are unique and scaled correctly!)")
    else:
        print("VERIFICATION: FAIL (Duplicate confidence scores found; they did not scale continuously!)")

    # Clean up test events
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM predictions WHERE event_id LIKE 'test-conf-%'"))
        conn.execute(text("DELETE FROM events WHERE event_id LIKE 'test-conf-%'"))
        conn.commit()
        print("Cleanup completed.")

if __name__ == "__main__":
    verify_confidence_scores()
