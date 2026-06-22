-- Aegis schema (matches alembic revision 4b3e2274e4f4)

CREATE TABLE IF NOT EXISTS events (
    event_id VARCHAR PRIMARY KEY,
    event_type VARCHAR,
    event_cause VARCHAR,
    corridor VARCHAR,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    requires_road_closure BOOLEAN,
    priority VARCHAR,
    start_datetime TIMESTAMP,
    end_datetime TIMESTAMP,
    description VARCHAR,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id SERIAL PRIMARY KEY,
    event_id VARCHAR REFERENCES events(event_id),
    predicted_duration_min DOUBLE PRECISION,
    predicted_disruption_class VARCHAR,
    confidence_score DOUBLE PRECISION,
    recommended_officers INTEGER,
    recommended_barricades JSONB,
    recommended_diversions JSONB,
    model_version VARCHAR,
    predicted_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id SERIAL PRIMARY KEY,
    event_id VARCHAR REFERENCES events(event_id),
    actual_duration_min DOUBLE PRECISION,
    actual_disruption_class VARCHAR,
    actual_officers_deployed INTEGER,
    notes VARCHAR,
    logged_by VARCHAR,
    logged_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recalibration_log (
    recal_id SERIAL PRIMARY KEY,
    event_cause VARCHAR,
    corridor VARCHAR,
    old_bias_correction DOUBLE PRECISION,
    new_bias_correction DOUBLE PRECISION,
    n_outcomes_used INTEGER,
    recalibrated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recal_cause_corridor
    ON recalibration_log (event_cause, corridor);
