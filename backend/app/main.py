import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.events import router as events_router
from backend.app.routers.predict import router as predict_router
from backend.app.routers.outcomes import router as outcomes_router
from backend.app.routers.recommend import router as recommend_router
from backend.app.routers.recalibration import router as recalibration_router
from backend.app.routers.learning_report import router as learning_report_router
from backend.app.routers.similar_events import router as similar_events_router

PROJECT_ROOT = Path("/Users/ritesh/.gemini/antigravity/scratch/aegis")

app = FastAPI(title="Aegis — Event Congestion Command System")

# Configure CORS for frontend dev server
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(events_router)
app.include_router(predict_router)
app.include_router(outcomes_router)
app.include_router(recommend_router)
app.include_router(recalibration_router)
app.include_router(learning_report_router)
app.include_router(similar_events_router)

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}

@app.get("/model_info", tags=["model_info"])
def get_model_info():
    duration_path = PROJECT_ROOT / "data" / "outputs" / "duration_model_single_day_feature_importance.json"
    severity_path = PROJECT_ROOT / "data" / "outputs" / "severity_model_feature_importance.json"
    
    if not duration_path.exists():
        raise HTTPException(status_code=404, detail="Duration model feature importance file not found.")
    if not severity_path.exists():
        raise HTTPException(status_code=404, detail="Severity model feature importance file not found.")
        
    try:
        with open(duration_path) as f:
            duration_info = json.load(f)
        with open(severity_path) as f:
            severity_info = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read feature importance files: {e}")
        
    return {
        "duration_model": duration_info,
        "severity_model": severity_info
    }
