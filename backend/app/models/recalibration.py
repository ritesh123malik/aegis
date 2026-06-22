from sqlalchemy import Column, Integer, String, Float, DateTime, func, Index
from backend.app.database import Base

class RecalibrationLog(Base):
    __tablename__ = "recalibration_log"

    recal_id = Column(Integer, primary_key=True, autoincrement=True)
    event_cause = Column(String, nullable=True)
    corridor = Column(String, nullable=True)
    old_bias_correction = Column(Float, nullable=True)
    new_bias_correction = Column(Float, nullable=True)
    n_outcomes_used = Column(Integer, nullable=True)
    recalibrated_at = Column(DateTime, nullable=True, server_default=func.now())

    __table_args__ = (
        Index("idx_recal_cause_corridor", "event_cause", "corridor"),
    )
