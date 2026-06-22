from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from backend.app.database import Base

class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=True)
    predicted_duration_min = Column(Float, nullable=True)
    predicted_disruption_class = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    recommended_officers = Column(Integer, nullable=True)
    recommended_barricades = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    recommended_diversions = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    model_version = Column(String, nullable=True)
    predicted_at = Column(DateTime, nullable=True, server_default=func.now())

