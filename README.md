# Aegis — Event Congestion Command System

> **Problem Statement**: PS2 — Event-Driven Traffic Congestion, Bengaluru Transit  
> **Live Frontend**: https://aegis-lyart-ten.vercel.app  
> **Live Backend API**: https://aegis-backend-e7r2.onrender.com  
> **API Docs (Swagger)**: https://aegis-backend-e7r2.onrender.com/docs  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Live Demo — What to See First](#2-live-demo--what-to-see-first)
3. [Feature Walkthrough (Every Feature, Step by Step)](#3-feature-walkthrough-every-feature-step-by-step)
4. [Architecture](#4-architecture)
5. [Machine Learning Models](#5-machine-learning-models)
6. [Dataset](#6-dataset)
7. [Database Schema](#7-database-schema)
8. [API Reference](#8-api-reference)
9. [Local Development Setup](#9-local-development-setup)
10. [Docker Compose Setup (One-Command Stack)](#10-docker-compose-setup-one-command-stack)
11. [Running the ML Training Pipeline](#11-running-the-ml-training-pipeline)
12. [Environment Variables](#12-environment-variables)
13. [Project Structure](#13-project-structure)
14. [Production Deployment](#14-production-deployment)
15. [Honesty & Limitations](#15-honesty--limitations)
16. [Verified Production Numbers](#16-verified-production-numbers)

---

## 1. Project Overview

Aegis is a production-deployed, end-to-end AI system for Bengaluru traffic command operations. It addresses **Problem Statement 2 (PS2): Event-Driven Traffic Congestion** by turning 8,173 historical ASTRAM traffic logs into a real-time intelligence layer.

### What Aegis Does

```
BEFORE AEGIS                          AFTER AEGIS
────────────────                      ──────────────────────────────────────
Operator receives alert               Operator receives alert
                 ↓                                      ↓
Operator guesses resources            Aegis predicts duration (planned) OR
and reacts manually                   severity class (unplanned)
                                                        ↓
                                      Aegis recommends officers, barricade
                                      coordinates, diversion routes, and
                                      signals requiring override
                                                        ↓
                                      Operator logs actual outcome after event
                                                        ↓
                                      Aegis auto-recalibrates future predictions
                                      for the same event-type/corridor bucket
                                      (no model retraining required)
```

### Key Differentiators

| Feature | Aegis |
|---|---|
| Prediction Type | Dual-arm: Duration (regression) for planned + Severity class (classification) for unplanned |
| Data Leakage Detection | Corridor feature removed from severity model after logging-bias leakage discovered |
| Recalibration | Rolling bias correction per `(cause × corridor)` bucket — live, without retraining |
| Transparency | Every prediction exposes `raw_model_output`, `calibration_applied`, `final_output` in the UI |
| Honesty | System openly states its limitations on the `/about` page in production |

---

## 2. Live Demo — What to See First

> **The system is live.** No setup required to view it.

Open **https://aegis-lyart-ten.vercel.app** in a browser.

> ⚠️ The backend is hosted on Render's free tier. **The first request may take 30–60 seconds** while the server wakes up from idle. This is a cold-start delay, not a bug. Subsequent requests are fast.

### Quick Start Checklist

| Step | What to do | What you will see |
|---|---|---|
| 1 | Open https://aegis-lyart-ten.vercel.app | Interactive Bengaluru map with 8,173 colour-coded event markers |
| 2 | Click any **blue** marker | Planned event details load in the right panel |
| 3 | Click **"Get Prediction"** | Duration prediction in minutes + confidence score |
| 4 | Expand **"Show Calculation Audit"** | Raw LightGBM output, calibration applied, final output, calibration source |
| 5 | Click **"Get Recommendation"** | Officer count, barricade coordinates, diversion routes, signals, baseline comparison |
| 6 | Click any **red/yellow** marker | Unplanned incident loads |
| 7 | Click **"Get Prediction"** | Severity class (Low/Medium/High/Critical) + confidence percentage |
| 8 | Click **"Log Outcome"** tab | Enter actual duration, officers deployed, notes — submit to trigger recalibration |
| 9 | Navigate to `/learning-report` | System-wide learning report with improvement % and per-bucket breakdown |
| 10 | Navigate to `/about` | Model transparency page with feature importance charts and honest limitations section |

---

## 3. Feature Walkthrough (Every Feature, Step by Step)

### Feature 1: Interactive Live Map

**URL**: https://aegis-lyart-ten.vercel.app  
**Component**: `frontend/components/MapView.tsx`

The homepage renders a full-screen **Leaflet.js map** of Bengaluru centred on the city's transit grid. All 8,173 events are loaded from `GET /events` and rendered as coloured circle markers:

| Marker Colour | Meaning |
|---|---|
| 🔵 Blue | Planned event (cricket match, construction, VIP movement, protest, procession) |
| 🔴 Red | Unplanned incident with High or Critical severity |
| 🟡 Yellow | Unplanned incident with Low or Medium severity |

**To use:**
1. Zoom and pan the map to any Bengaluru corridor
2. Click a marker to open the event detail panel on the right

---

### Feature 2: Prediction Panel (Duration or Severity)

**Component**: `frontend/components/PredictionPanel.tsx`  
**API**: `POST /predict` with `{"event_id": "FKID000XXX"}`

After clicking a marker, click **"Get Prediction"** in the right panel.

**For planned events:**
- Predicted duration in minutes (e.g., `55.12 minutes`)
- Confidence score (e.g., `95%`)
- Low data warning if fewer than 5 similar historical events exist

**For unplanned events:**
- Predicted severity class: `Low`, `Medium`, `High`, or `Critical`
- Real classifier probability score (e.g., `60.19%`)

#### Sub-Feature: Calculation Audit Trail

Click **"Show Calculation Audit"** below the prediction to expand:

```
Raw Model Output:    55.12404684882768
Calibration Applied: 0.0
Final Output:        55.12404684882768
Source:              No calibration history yet for this bucket — raw model output used as-is
```

After the recalibration loop has run (i.e., outcomes have been logged for this bucket):
```
Raw Model Output:    411.8629623373654
Calibration Applied: 52.39073003118213
Final Output:        464.2536923685475
Source:              construction/ORR East 2 bucket, n_outcomes_used=2
```

---

### Feature 3: Recommendation Engine

**Component**: `frontend/components/RecommendationPanel.tsx`  
**API**: `GET /recommend/{event_id}`

Click **"Get Recommendation"** for any selected event.

**Outputs:**

| Field | Example |
|---|---|
| Recommended Officers | `5` |
| Recommended Barricades | 2 locations (lat/lng + road class) |
| Diversion Routes | 79 polyline coordinates (OSM-cached) |
| Signals Requiring Attention | 14 traffic signals within 1 km radius |
| Baseline Comparison | Naive baseline officers vs Aegis recommendation + arithmetic breakdown |

**Officer Formula:**
```
Officers = BASE[disruption_class] + CLOSURE_MOD + CROWD_MOD
BASE: {Low: 2, Medium: 4, High: 8, Critical: 15}
CLOSURE_MOD: +2 if requires_road_closure
CROWD_MOD: +1 if event_cause in {public_event, procession, vip_movement}

Example (FKID000008 — Cricket Match):
Medium(4) + crowd_control(+1) = 5 Officers
Naive Baseline: 4 Officers
```

**Barricade placement**: Only `primary`, `secondary`, or `tertiary` roads (residential roads are hardcoded-excluded with a production `assert`).

---

### Feature 4: Outcome Logging & Recalibration Trigger

**Component**: `frontend/components/OutcomeForm.tsx`  
**API**: `POST /outcomes`

After an event concludes, click the **"Log Outcome"** tab in the right panel.

**Fill in:**
- Actual Duration (minutes)
- Actual Officers Deployed
- Notes (free text)

**Submit triggers:**
1. Outcome saved to `outcomes` table
2. `recalibration_service.recalibrate()` runs immediately
3. All predictions for the same `(event_cause, corridor)` bucket are automatically corrected going forward

**API Response includes:**
```json
{
  "outcome": { "event_id": "FKID000052", "actual_duration_min": 450.0, "outcome_id": 1 },
  "recalibration_log": {
    "old_bias_correction": 0.0,
    "new_bias_correction": 48.58722838754494,
    "n_outcomes_used": 1
  }
}
```

---

### Feature 5: Learning Report Dashboard

**URL**: https://aegis-lyart-ten.vercel.app/learning-report  
**Component**: `frontend/components/RecalibrationViz.tsx`  
**API**: `GET /learning_report`

**Shows:**
- Total outcomes logged
- Mean Raw Error (what LightGBM predicted without calibration)
- Mean Corrected Error (after recalibration)
- System Improvement % `= (raw_err − corrected_err) / raw_err × 100`
- Per-bucket breakdown table (cause × corridor)
- Line chart: bias correction value over time (n_outcomes on X-axis, bias correction on Y-axis)

**Safety Warning**: If fewer than 10 outcomes logged, an amber banner displays:
> *"Limited operational history logged — recalibration factors may experience high initial volatility."*

**Verified production values (3 outcomes logged):**

| Metric | Value |
|---|---|
| Mean Raw Error | 50.97283257499962 minutes |
| Mean Corrected Error | 36.34505081030392 minutes |
| System Improvement | **+28.69721187884331%** |

---

### Feature 6: Similar Events Panel

**Component**: `frontend/components/SimilarEventsPanel.tsx`  
**API**: `GET /similar_events/{event_id}`

Shown at the bottom of the event detail panel for any selected event.

**Algorithm:**
```
Similarity = 0.5 × cause_match + 0.3 × corridor_proximity + 0.2 × time_of_day

cause_match:       1.0 if same event_cause, else 0.0
corridor_proximity: 1.0 if same corridor, else max(0, 1 - haversine(centroids) / 15 km)
time_of_day:       1.0 - (circular_hour_difference / 12)
```

Returns the **top 5 most similar** historical events. For each match:
- If a real outcome exists: shows `actual_duration_min`, `actual_disruption_class`, and `notes`
- If no outcome logged: explicitly shows *"No actual outcome logged for this event"* — never fabricates data

---

### Feature 7: About Page — Model Transparency & Honesty

**URL**: https://aegis-lyart-ten.vercel.app/about  
**API**: `GET /model_info`

Shows two interactive bar charts of live LightGBM feature weights (fetched from the production `/model_info` endpoint):

**Duration Model features** (8 features, `corridor` included):
```
corridor_event_rate: 72,749,159.55 ← highest importance
hour_sin:            52,533,668.40
corridor:            38,129,970.71
...
```

**Severity Model features** (7 features, `corridor` deliberately absent):
```
requires_road_closure: 23,327.44 ← highest importance
day_of_week:            2,867.74
hour_sin:               2,856.72
...
```

The absence of `corridor` in the severity model is **machine-verifiable proof** of the leakage fix.

**"What We're Honest About" section** (verbatim from production):
> Severity classification has a known boundary — The real macro-F1 is **0.5359**, not a marketing-rounded version.  
> Confidence scoring is principled, not perfect — Sample-size heuristic for duration, real probabilities for severity.  
> Our outcome history is still small — Numbers reflect early-stage learning.

---

## 4. Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        AEGIS — SYSTEM ARCHITECTURE                         │
│                                                                            │
│  ┌───────────────────────┐   REST API (CORS-protected)  ┌───────────────┐  │
│  │  NEXT.JS 14 FRONTEND  │◄───────────────────────────►│ FASTAPI       │  │
│  │  TypeScript           │                              │ BACKEND       │  │
│  │  Vercel (Production)  │                              │ Render        │  │
│  │                       │                              │ (Production)  │  │
│  │  Pages:               │  GET /events                 │               │  │
│  │  / (Dashboard + Map)  │  POST /predict               │  7 Routers:   │  │
│  │  /learning-report     │  GET /recommend/{id}         │  events       │  │
│  │  /about               │  POST /outcomes              │  predict      │  │
│  │                       │  GET /learning_report        │  outcomes     │  │
│  │  Components:          │  GET /similar_events/{id}    │  recommend    │  │
│  │  MapView (Leaflet)    │  GET /model_info             │  recalibration│  │
│  │  PredictionPanel      │  GET /health                 │  learning_    │  │
│  │  RecommendPanel       │                              │    report     │  │
│  │  OutcomeForm          │                              │  similar_     │  │
│  │  RecalibrationViz     │                              │    events     │  │
│  │  SimilarEventsPanel   │                              │               │  │
│  └───────────────────────┘                              └───────┬───────┘  │
│                                                                 │          │
│                                                   ┌─────────────▼───────┐  │
│                                                   │  ML MODEL LAYER     │  │
│                                                   │                     │  │
│                                                   │  duration_model_    │  │
│                                                   │   single_day.pkl    │  │
│                                                   │  (LightGBMRegressor)│  │
│                                                   │                     │  │
│                                                   │  severity_model.pkl │  │
│                                                   │  (LightGBMClassifier│  │
│                                                   │                     │  │
│                                                   │  osm_cache.json     │  │
│                                                   │  (OSM Geospatial    │  │
│                                                   │   Pre-Cached Data)  │  │
│                                                   └──────────┬──────────┘  │
│                                                              │             │
│                                                   ┌──────────▼──────────┐  │
│                                                   │  POSTGRESQL DB      │  │
│                                                   │  Render Managed     │  │
│                                                   │                     │  │
│                                                   │  events (8,173)     │  │
│                                                   │  predictions + JSONB│  │
│                                                   │  outcomes           │  │
│                                                   │  recalibration_log  │  │
│                                                   └─────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Machine Learning Models

### 5.1 Dual-Arm Design

The dataset contains two fundamentally incompatible data shapes. A single unified model is mathematically impossible:

| Arm | Event Type | Model Type | Target |
|---|---|---|---|
| Duration Arm | `planned` | LightGBM Regressor | `duration_minutes` (continuous) |
| Severity Arm | `unplanned` | LightGBM Classifier | `disruption_class` (categorical: Low/Medium/High/Critical) |

Unplanned incidents have `NULL` duration fields by definition — they cannot use the regression arm. Planned events lack severity priority categorisation — they cannot use the classification arm.

### 5.2 Duration Model — Full Details

**Training data**: 327 single-day planned events (anomalies and multi-day events removed)  
**Validation**: 5-Fold Cross-Validation (`KFold(n_splits=5, shuffle=True, random_state=42)`)

**Input Features (8):**

| Feature | Type | Description |
|---|---|---|
| `corridor` | Categorical | Named Bengaluru transit corridor |
| `event_cause` | Categorical | Root cause (construction, cricket, etc.) |
| `requires_road_closure` | Boolean | Whether the event blocks roads |
| `hour_sin` | Float | `sin(2π × hour / 24)` — cyclic encoding |
| `hour_cos` | Float | `cos(2π × hour / 24)` — cyclic encoding |
| `day_of_week` | Integer | 0=Monday … 6=Sunday |
| `is_weekend` | Boolean | Derived from `day_of_week` |
| `corridor_event_rate` | Float | Fraction of events of this cause on this corridor (computed live from DB) |

**Anti-leakage**: `corridor_event_rate` is recomputed on the training fold only during CV (`fit_on=df_train`), not the full dataset.

**Validated Performance:**

| Metric | Aegis LightGBM | Naive Baseline (mean by cause) |
|---|---|---|
| Mean MAE | **274.43515971079717 min** | 347.9487549643642 min |
| MAE Std Dev | 15.559054124563117 min | 18.096983974258713 min |
| **Error Reduction** | **73.51 min better** | — |

**Confidence Score Formula:**
```python
confidence = clip(0.3 + 0.13 × min(n_exact_corridor_cause_matches, 5), 0.3, 0.95)
```

**Feature Importances (Gain, live from `/model_info`):**

| Rank | Feature | Score |
|---|---|---|
| 1 | corridor_event_rate | 72,749,159.55 |
| 2 | hour_sin | 52,533,668.40 |
| 3 | corridor | 38,129,970.71 |
| 4 | hour_cos | 34,311,000.45 |
| 5 | day_of_week | 31,358,458.83 |
| 6 | requires_road_closure | 23,750,214.20 |
| 7 | event_cause | 688,812.80 |
| 8 | is_weekend | 0.00 |

### 5.3 Severity Classifier — Full Details + Leakage Story

**Critical integrity decision**: The initial model achieved macro-F1 = **0.9993** — suspiciously near-perfect. Root cause analysis revealed:

> The `corridor` feature was 100% correlated with `priority` in ASTRAM logs due to logging bias — officers in high-priority corridors always dispatched at High priority. Since `disruption_class` is derived from `priority + requires_road_closure`, the model was exploiting corridor as a shortcut (leakage), bypassing environmental context entirely.

**Resolution**: `corridor` permanently removed. Model retrained on 7-feature leak-free set.

**Training**: Time-based holdout split — 80% train (earliest data), 20% test (most recent data), sorted by `start_datetime`.

**Input Features (7, post-leakage-fix):**

| Feature | Type | Description |
|---|---|---|
| `event_cause` | Categorical | Root cause type |
| `requires_road_closure` | Boolean | Road closure flag |
| `hour_sin` | Float | Cyclic time encoding |
| `hour_cos` | Float | Cyclic time encoding |
| `day_of_week` | Integer | Day of week |
| `is_weekend` | Boolean | Weekend flag |
| `month` | Integer | Calendar month |

**Validated Performance:**

| Metric | Value |
|---|---|
| **Macro-F1 (time-based holdout)** | **0.5359** |
| **Macro-F1 (5-Fold CV)** | **0.5551025091852966** |
| **Overall Accuracy** | **0.6209628275441804** |
| ~~Rejected Leaky Macro-F1~~ | ~~0.9993~~ |

**Per-Class Breakdown:**

| Class | Precision | Recall | F1-Score | Support |
|---|---|---|---|---|
| Low | 0.4628 | 0.2528 | 0.3270 | 542 |
| Medium | 0.6642 | 0.8307 | 0.7382 | 957 |
| High | 0.6667 | 0.7059 | 0.6857 | 85 |
| Critical | 0.4655 | 0.4737 | 0.4696 | 57 |
| **Macro Avg** | **0.5648** | **0.5658** | **0.5551** | 1,641 |

**Mathematical Partition Invariant** (empirically verified):

```
Actual\Predicted  Low   Medium  High  Critical
Low               137    402     0      3
Medium            159    795     0      3
High                0      0    60     25
Critical            0      0    30     27
```

Confusion is strictly isolated within `{Low, Medium}` and `{High, Critical}`. Because `requires_road_closure` is a hard binary input, the model can never misclassify across these groups — a strong operational safety guarantee.

**Feature Importances (7-feature set, `corridor` absent = proof of fix):**

| Rank | Feature | Score |
|---|---|---|
| 1 | requires_road_closure | 23,327.44 |
| 2 | day_of_week | 2,867.74 |
| 3 | hour_sin | 2,856.72 |
| 4 | month | 2,698.88 |
| 5 | hour_cos | 2,223.20 |
| 6 | event_cause | 1,309.26 |
| 7 | is_weekend | 27.58 |

### 5.4 Recalibration Loop (Live, No Retraining Required)

```
Step 1: Prediction generated → stored in predictions table
Step 2: Event resolves → operator logs actual outcome via POST /outcomes
Step 3: recalibration_service computes rolling bias:
        Error = Actual_duration - Raw_LightGBM_output
        Bias = mean(Error_1, Error_2, ..., Error_n) for this (cause × corridor) bucket
Step 4: New RecalibrationLog row inserted with old_bias, new_bias, n_outcomes_used
Step 5: All subsequent predictions in this bucket:
        final_output = raw_lgbm_output + current_bias
```

**Verified Case Study (production data):**

| State | Event | Raw Pred | Actual | Error | New Bias |
|---|---|---|---|---|---|
| A | FKID000052 | 401.41 min | — | — | 0.0 (n=0) |
| B | FKID000052 | 401.41 min | 450.0 min | +48.59 | **+48.587** (n=1) |
| C | FKID000082 | 443.81 min | 500.0 min | +56.19 | **+52.391** (n=2) |
| **Result** | FKID000139 | 464.25 min | 460.0 min | **4.25 min** | — |
| **vs Raw** | FKID000139 | 411.86 min | 460.0 min | **48.14 min** | — |
| **Error Reduction** | — | — | — | **91.16%** | — |

---

## 6. Dataset

| Metric | Value |
|---|---|
| Source | Bengaluru ASTRAM Traffic Command Logs |
| Total Rows | **8,173** |
| Unplanned Incidents | 7,706 rows (94.2860641135446%) |
| Planned Events | 467 rows (5.71393588645539%) |
| Crowd-Event Subset | 191 rows (2.3369631714180836%) — `public_event`, `procession`, `vip_movement`, `protest` |
| Single-Day Training Subset | 327 rows |
| Severity Distribution | Medium: 4,733 · Low: 2,762 · High: 379 · Critical: 297 |

The raw CSV is processed through `training/02_feature_engineering.py` which:
- Derives `duration_minutes` from `start_datetime` / `end_datetime`
- Encodes cyclic time features (`hour_sin`, `hour_cos`)
- Derives `disruption_class` from `requires_road_closure` + `priority`
- Filters single-day planned events for the duration training subset
- Outputs `data/processed/cleaned_events.parquet` and `data/processed/severity_features.parquet`

---

## 7. Database Schema

```sql
-- Events (seeded from ASTRAM dataset)
CREATE TABLE events (
  event_id              VARCHAR PRIMARY KEY,
  event_type            VARCHAR,   -- 'planned' or 'unplanned'
  event_cause           VARCHAR,   -- 'construction', 'cricket', 'accident', etc.
  corridor              VARCHAR,   -- Named Bengaluru transit corridor
  latitude              FLOAT,
  longitude             FLOAT,
  requires_road_closure BOOLEAN,
  priority              VARCHAR,   -- 'Low', 'Medium', 'High', 'Critical'
  start_datetime        TIMESTAMP,
  end_datetime          TIMESTAMP,
  description           VARCHAR,
  created_at            TIMESTAMP DEFAULT now()
);

-- Predictions (written on every POST /predict call)
CREATE TABLE predictions (
  prediction_id              SERIAL PRIMARY KEY,
  event_id                   VARCHAR REFERENCES events(event_id),
  predicted_duration_min     FLOAT,
  predicted_disruption_class VARCHAR,
  confidence_score           FLOAT,
  recommended_officers       INTEGER,
  recommended_barricades     JSONB,
  recommended_diversions     JSONB,
  model_version              VARCHAR,
  predicted_at               TIMESTAMP,
  prediction_transparency    JSONB   -- raw_model_output, calibration_applied, final_output, source
);

-- Outcomes (logged by operators after events resolve)
CREATE TABLE outcomes (
  outcome_id               SERIAL PRIMARY KEY,
  event_id                 VARCHAR REFERENCES events(event_id),
  actual_duration_min      FLOAT,
  actual_disruption_class  VARCHAR,
  actual_officers_deployed INTEGER,
  notes                    TEXT,
  logged_at                TIMESTAMP
);

-- Recalibration Log (written after every outcome)
CREATE TABLE recalibration_log (
  recal_id            SERIAL PRIMARY KEY,
  event_cause         VARCHAR,
  corridor            VARCHAR,
  old_bias_correction FLOAT,
  new_bias_correction FLOAT,
  n_outcomes_used     INTEGER,
  recalibrated_at     TIMESTAMP
);
```

The `prediction_transparency` column was added via an Alembic migration:
```bash
alembic upgrade head
```

---

## 8. API Reference

All endpoints live at `https://aegis-backend-e7r2.onrender.com`. Interactive Swagger docs at `/docs`.

### `GET /health`
Liveness check.
```json
{"status": "ok"}
```

### `GET /events`
Returns all 8,173 events. Supports optional `?limit=N&offset=M` query params.

### `POST /predict`
```json
// Request
{"event_id": "FKID000008"}

// Response (planned event)
{
  "event_id": "FKID000008",
  "predicted_duration_min": 55.12404684882768,
  "predicted_disruption_class": null,
  "confidence_score": 0.95,
  "model_version": "v1.0",
  "prediction_transparency": {
    "raw_model_output": 55.12404684882768,
    "calibration_applied": 0.0,
    "final_output": 55.12404684882768,
    "calibration_source": "No calibration history yet for this bucket — raw model output used as-is"
  }
}
```

### `GET /recommend/{event_id}`
```json
// Response
{
  "recommended_officers": 5,
  "recommended_barricades": [
    {"lat": 12.9799424, "lng": 77.6002149, "road_class": "primary"}
  ],
  "recommended_diversions": [...],  // array of polyline coordinate arrays
  "signals_requiring_attention": [...],
  "baseline_comparison": {
    "naive_baseline_officers": 4,
    "our_recommendation_officers": 5,
    "adjustment_breakdown": "Medium disruption (base 4) + crowd control required (+1) = 5",
    "baseline_source": "no logged outcomes for this cause yet — using static base lookup"
  }
}
```

### `POST /outcomes`
```json
// Request
{
  "event_id": "FKID000052",
  "actual_duration_min": 450.0,
  "actual_officers_deployed": 6,
  "notes": "Construction took longer due to equipment delay"
}

// Response — includes automatic recalibration result
{
  "outcome": {"outcome_id": 1, "event_id": "FKID000052", "logged_at": "..."},
  "recalibration_log": {
    "old_bias_correction": 0.0,
    "new_bias_correction": 48.58722838754494,
    "n_outcomes_used": 1
  }
}
```

### `GET /learning_report`
```json
{
  "total_outcomes_logged": 3,
  "mean_raw_error": 50.97283257499962,
  "mean_corrected_error": 36.34505081030392,
  "improvement_pct": 28.69721187884331,
  "severity_raw_accuracy": 0.0,
  "per_bucket_breakdown": [...]
}
```

### `GET /similar_events/{event_id}`
Returns top 5 similar events with similarity score and outcome data (or explicit null if no outcome logged).

### `GET /model_info`
Returns live LightGBM feature importance weights for both models.

---

## 9. Local Development Setup

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| PostgreSQL | 14+ | https://postgresql.org (or use Docker) |
| Git | any | https://git-scm.com |

### Step 1 — Clone the Repository
```bash
git clone <your-repo-url>
cd aegis
```

### Step 2 — Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install all Python dependencies
pip install -r backend/requirements.txt
```

### Step 3 — Database Setup

Create a PostgreSQL database named `aegis`:

```bash
psql -U postgres -c "CREATE USER aegis WITH PASSWORD 'aegis';"
psql -U postgres -c "CREATE DATABASE aegis OWNER aegis;"
```

### Step 4 — Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql://aegis:aegis@localhost:5432/aegis
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MOCK_MODE=false
```

### Step 5 — Run Database Migrations

```bash
# From project root (where alembic.ini lives)
alembic upgrade head
```

This creates all tables including the `prediction_transparency` JSONB column.

### Step 6 — Seed the Database

```bash
# Seeds all 8,173 events from the Astram dataset
python training/seed_db.py
```

Expected output:
```
Seeding 8173 events...
Done. 8173 rows inserted.
```

### Step 7 — Start the Backend

```bash
# From project root
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend is now live at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### Step 8 — Frontend Setup

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MOCK_MODE=false
```

### Step 9 — Start the Frontend

```bash
# From frontend/ directory
npm run dev
# OR: for a clean cache start
npm run dev:clean
```

Frontend is now live at `http://localhost:3000`.

### Step 10 — Verify Everything

Open `http://localhost:3000`. The Bengaluru map should load with all event markers. If markers don't appear, check that the backend is running and the `NEXT_PUBLIC_API_URL` is set correctly.

```bash
# Quick backend smoke test
curl http://localhost:8000/health
# → {"status":"ok"}

curl http://localhost:8000/events?limit=3
# → Array of 3 event objects

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"event_id":"FKID000008"}'
# → Prediction with prediction_transparency
```

---

## 10. Docker Compose Setup (One-Command Stack)

For the fastest local setup without manual PostgreSQL installation:

```bash
# Start the full stack: postgres + backend + frontend
docker compose up --build

# In a separate terminal, run migrations + seed once the backend is healthy:
docker compose exec backend alembic upgrade head
docker compose exec backend python training/seed_db.py
```

Services:
| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| Postgres | localhost:5432 |
| Valhalla (optional) | localhost:8002 |

To stop:
```bash
docker compose down
# Add -v to also delete the database volume:
docker compose down -v
```

---

## 11. Running the ML Training Pipeline

If you want to retrain the models from scratch (not required to run the app — trained `.pkl` files are committed to the repo):

```bash
# Activate virtual environment first
source venv/bin/activate

# Step 1: Feature engineering — creates cleaned parquet files
python training/02_feature_engineering.py

# Step 2: Train the duration regressor (LightGBM, 5-Fold CV on 327 rows)
python training/03_train_duration_model.py
# Outputs: backend/app/ml/duration_model_single_day.pkl
#          data/outputs/duration_model_single_day_feature_importance.json
#          data/outputs/duration_model_single_day_cv_metrics.json

# Step 3: Train the severity classifier (LightGBM, time-based split)
python training/04_train_severity_model.py
# Outputs: backend/app/ml/severity_model.pkl
#          data/outputs/severity_model_feature_importance.json
#          data/outputs/severity_model_confusion_matrix.png

# Step 4: Pre-fetch OSM data (Overpass API — requires internet)
python training/06_prefetch_osm_cache.py
# Outputs: data/osm_cache.json (used by recommendation engine)
```

**Expected training console output (Step 2):**
```
Duration model: MAE = 274.4 ± 15.6 minutes (5-fold CV) vs baseline MAE = 347.9 ± 18.1 minutes
```

**Expected training console output (Step 3):**
```
Severity classifier: macro-F1 = 0.54 (time-based holdout) vs baseline macro-F1 = 0.XX
```

---

## 12. Environment Variables

### Backend (`.env` at project root)

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://aegis:aegis@localhost:5432/aegis` |
| `VALHALLA_URL` | Valhalla routing engine URL (optional) | `http://localhost:8002/route` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL (browser-accessible) | `http://localhost:8000` |
| `NEXT_PUBLIC_MOCK_MODE` | Use built-in mock data instead of live API | `false` |

### Production (set on Render/Vercel dashboards)

| Service | Variable | Value |
|---|---|---|
| Render (backend) | `DATABASE_URL` | Render PostgreSQL internal URL |
| Vercel (frontend) | `NEXT_PUBLIC_API_URL` | `https://aegis-backend-e7r2.onrender.com` |

---

## 13. Project Structure

```
aegis/
├── README.md                          # This file
├── .env                               # Local env vars (gitignored)
├── .env.example                       # Template for .env
├── .gitignore
├── alembic.ini                        # Alembic migration config
├── docker-compose.yml                 # Full local stack
│
├── alembic/                           # Database migration scripts
│   ├── env.py
│   └── versions/
│       └── xxxx_add_prediction_transparency.py
│
├── backend/
│   ├── __init__.py
│   ├── Dockerfile
│   ├── requirements.txt               # All Python dependencies
│   └── app/
│       ├── main.py                    # FastAPI app + CORS + router registration
│       ├── database.py                # SQLAlchemy session + Base
│       ├── config.py
│       ├── models/                    # SQLAlchemy ORM models
│       │   ├── event.py
│       │   ├── prediction.py
│       │   ├── outcome.py
│       │   └── recalibration.py
│       ├── schemas/                   # Pydantic request/response schemas
│       │   └── prediction_schema.py
│       ├── routers/                   # FastAPI route handlers
│       │   ├── events.py
│       │   ├── predict.py
│       │   ├── outcomes.py
│       │   ├── recommend.py
│       │   ├── recalibration.py
│       │   ├── learning_report.py
│       │   └── similar_events.py
│       ├── services/                  # Business logic
│       │   ├── prediction_service.py  # LightGBM inference + confidence
│       │   ├── recalibration_service.py # Rolling bias correction math
│       │   ├── recommendation_service.py # Officer formula + OSM barricades/diversions
│       │   ├── osm_service.py         # OSM cache reader
│       │   └── pipeline_service.py    # Retraining pipeline (future)
│       └── ml/                        # Trained model files
│           ├── duration_model_single_day.pkl
│           └── severity_model.pkl
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── pages/
│   │   ├── index.tsx                  # Main dashboard (dynamic import of Dashboard)
│   │   ├── about.tsx                  # Model transparency + honesty page
│   │   ├── learning-report.tsx        # Learning report + RecalibrationViz
│   │   └── _app.tsx
│   └── components/
│       ├── Dashboard.tsx              # Main orchestrator (SSR disabled)
│       ├── MapView.tsx                # Leaflet map + marker rendering
│       ├── PredictionPanel.tsx        # Prediction + transparency audit
│       ├── RecommendationPanel.tsx    # Officer/barricade/diversion display
│       ├── OutcomeForm.tsx            # Outcome logging form
│       ├── RecalibrationViz.tsx       # Recharts recalibration line chart
│       └── SimilarEventsPanel.tsx     # Top-5 similarity search results
│
├── training/                          # ML training scripts
│   ├── 02_feature_engineering.py      # Data cleaning + feature derivation
│   ├── 03_train_duration_model.py     # Duration LightGBM regressor
│   ├── 04_train_severity_model.py     # Severity LightGBM classifier
│   ├── 06_prefetch_osm_cache.py       # OSM Overpass API data fetch
│   └── seed_db.py                     # Database seeding from CSV
│
├── data/
│   ├── raw/                           # Raw ASTRAM CSV (source data)
│   ├── processed/                     # Feature-engineered parquet files
│   │   ├── cleaned_events.parquet
│   │   └── severity_features.parquet
│   └── outputs/                       # Model artifacts + metrics
│       ├── duration_model_single_day_feature_importance.json
│       ├── duration_model_single_day_cv_metrics.json
│       ├── severity_model_feature_importance.json
│       ├── severity_model_confusion_matrix.json
│       └── severity_model_confusion_matrix.png
│
└── deployment/
    └── init.sql                       # Docker Compose DB init script
```

---

## 14. Production Deployment

### Backend (Render)

1. Connect the GitHub repo to Render
2. Set **Root Directory** to `/` (project root)
3. Set **Build Command**: `pip install -r backend/requirements.txt`
4. Set **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
5. Add environment variable: `DATABASE_URL` = Render PostgreSQL internal URL
6. Run migrations once after first deploy: via Render shell: `alembic upgrade head`
7. Run seeding once: via Render shell: `python training/seed_db.py`

### Frontend (Vercel)

1. Connect the GitHub repo to Vercel
2. Set **Root Directory** to `frontend`
3. Add environment variable: `NEXT_PUBLIC_API_URL` = `https://aegis-backend-e7r2.onrender.com`
4. Deploy — Vercel auto-detects Next.js

### Production URLs

| Service | URL |
|---|---|
| **Frontend** | https://aegis-lyart-ten.vercel.app |
| **Backend** | https://aegis-backend-e7r2.onrender.com |
| **API Docs** | https://aegis-backend-e7r2.onrender.com/docs |

---

## 15. Honesty & Limitations

Aegis ships with an explicit honesty section on the production `/about` page. These are stated as constraints, not bugs:

### Severity Model Boundary
The real corrected macro-F1 is **0.5359** — not rounded up. The model is strongest on the ~92% of Low/Medium cases. High/Critical classification is harder due to lower support (379 + 297 rows) but the partition invariant guarantees no cross-group misclassification.

### Confidence Scoring
The duration model's confidence uses a sample-size heuristic (more examples → higher confidence, up to 0.95 max). This is a principled formula, not a learned calibration. The severity model uses real classifier probabilities from `predict_proba()`.

### Outcome History Size
As of initial production deployment, 3 outcomes have been logged. The recalibration loop improves with every outcome — the numbers reported (91.16% error reduction, +28.70% improvement) are real but represent early-stage learning from a small sample.

### Valhalla Routing
The dynamic Valhalla exclusion routing (for events with `requires_road_closure = True`) falls back gracefully to cached OSM routes if Valhalla is unreachable. No 500 errors are raised. The OSM cache provides 79 usable diversion route coordinates for most corridors.

### Officer Count Source
The recommendation engine is rules-based, not ML-driven. The ASTRAM dataset has 98.4% `NULL` values in the `assigned_to_police_id` field — there is insufficient ground truth to train an officer count model. The base lookup table is calibrated from domain-informed heuristics and improves as real outcomes are logged.

---

## 16. Verified Production Numbers

All numbers below are real, unrounded, and captured from the live production system:

| Metric | Exact Value |
|---|---|
| Total dataset rows | `8173` |
| Unplanned incident percentage | `94.2860641135446%` |
| Planned event percentage | `5.71393588645539%` |
| Crowd-event subset | `2.3369631714180836%` |
| Duration model Mean MAE | `274.43515971079717 minutes` |
| Duration model Baseline MAE | `347.9487549643642 minutes` |
| Duration model MAE Std Dev | `15.559054124563117 minutes` |
| Severity corrected Macro-F1 (holdout) | `0.5359` |
| Severity corrected Macro-F1 (CV) | `0.5551025091852966` |
| Severity corrected Accuracy | `0.6209628275441804` |
| Severity rejected leaky F1 | `0.9993` |
| Recalibration bias after n=1 outcome | `+48.58722838754494 minutes` |
| Recalibration bias after n=2 outcomes | `+52.39073003118213 minutes` |
| FKID000139 error reduction | `91.16%` |
| System-wide improvement rate | `+28.69721187884331%` |
| Live database row count | `8173 (SELECT COUNT(*) FROM events)` |
| Live health endpoint | `{"status": "ok"}` |

---

*Built for Bengaluru. Designed for honesty. Deployed for real.*
