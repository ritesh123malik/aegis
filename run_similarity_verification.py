import requests
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
backend_url = "http://localhost:8000"

def run_verification():
    # 3 target events to test
    target_ids = ["FKID000008", "FKID7248" if False else "FKID007248", "FKID000000"]
    
    for eid in target_ids:
        url = f"{backend_url}/similar_events/{eid}"
        print(f"\n======================================================================")
        print(f"QUERYING SIMILAR EVENTS FOR TARGET: {eid}")
        print(f"======================================================================")
        
        # We can also fetch the target event's details to print them
        r_event = requests.get(f"{backend_url}/events")
        target_event = None
        if r_event.status_code == 200:
            for ev in r_event.json():
                if ev["event_id"] == eid:
                    target_event = ev
                    break
        
        if target_event:
            print(f"Target Details: Cause: {target_event.get('event_cause')} | Corridor: {target_event.get('corridor')} | Type: {target_event.get('event_type')}")
        
        r = requests.get(url)
        if r.status_code != 200:
            print(f"Error: {r.status_code} - {r.text}")
            continue
            
        sims = r.json()
        print(f"Returned {len(sims)} similar past events:\n")
        
        for idx, sim in enumerate(sims):
            print(f"  {idx+1}. Event ID: {sim['event_id']}")
            print(f"     Corridor: {sim['corridor']:<25} | Cause: {sim['event_cause']:<20} | Type: {sim['event_type']}")
            print(f"     Similarity Score: {sim['similarity_score']:.4f} ({sim['similarity_score']*100:.1f}% Match)")
            
            outcome = sim["outcome"]
            if outcome:
                print(f"     [REAL OUTCOME ON RECORD]")
                print(f"       Actual Duration: {outcome.get('actual_duration_min')} min")
                print(f"       Actual Severity: {outcome.get('actual_disruption_class')}")
                print(f"       Notes: \"{outcome.get('notes')}\"")
            else:
                print(f"     [No real outcome on record]")
            print()

if __name__ == "__main__":
    run_verification()
