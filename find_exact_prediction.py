import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_URL = "postgresql://aegis:aegis@localhost:5432/aegis"
engine = create_engine(DATABASE_URL)

model = joblib.load("backend/app/ml/duration_model_single_day.pkl")

# Calculate corridor event rate from DB
with engine.connect() as conn:
    num = conn.execute(text("SELECT COUNT(*) FROM events WHERE corridor='Varthur Road' AND event_cause='others'")).fetchone()[0]
    den = conn.execute(text("SELECT COUNT(*) FROM events WHERE corridor='Varthur Road'")).fetchone()[0]
rate = num / den if den > 0 else 0.0
print(f"Rate: {rate}")

# Let's grid search hour (0-23), day_of_week (0-6), is_weekend (True/False)
for hour in range(24):
    for day in range(7):
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        is_we = day in [5, 6]
        
        input_data = pd.DataFrame([{
            "corridor": "Varthur Road",
            "event_cause": "others",
            "requires_road_closure": True,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "day_of_week": day,
            "is_weekend": is_we,
            "corridor_event_rate": rate
        }])
        
        input_data["corridor"] = input_data["corridor"].astype("category")
        input_data["event_cause"] = input_data["event_cause"].astype("category")
        
        pred = model.predict(input_data)[0]
        if abs(pred - 240.84) < 1.0:
            print(f"FOUND: Hour={hour}, Day={day}, Pred={pred}")
