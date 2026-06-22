from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.events import router as events_router
from backend.app.routers.predict import router as predict_router
from backend.app.routers.outcomes import router as outcomes_router
from backend.app.routers.recommend import router as recommend_router
from backend.app.routers.recalibration import router as recalibration_router

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

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
