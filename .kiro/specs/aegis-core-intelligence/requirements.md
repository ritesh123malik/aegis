# Requirements Document

## Introduction

This document defines the requirements for **Phase 1: Core Intelligence** of the Aegis Event Congestion Command System. Aegis is a FastAPI/Python backend with a Next.js/React frontend that predicts traffic disruption severity and duration for planned and unplanned events in Bengaluru, generates rules-based resource recommendations (officers, barricades, diversions), and learns from logged outcomes via a recalibration loop.

Phase 1 adds four interconnected capabilities to the existing system:

1. **Explainable Resource Engine** — an auditable, structured reasoning tree that surfaces *why* each officer/barricade count was recommended, replacing opaque string summaries.
2. **Spatial Intelligence for Barricades & Diversions** — a graph-aware junction registry and live Valhalla routing integration that constrains recommendations to topologically valid road-network nodes.
3. **Historical Learning & Command Center Dashboard** — a centralised frontend store (Zustand) that unifies live predictions, active recommendations, and historical outcomes, plus a percentage-error metric for the learning loop.
4. **Interactive Congestion Heatmap** — a `react-leaflet-heat` layer that converts predicted disruption scores to a 0–1 weight and renders dynamically as the operator selects different corridors.

Phase 2 items (Digital Twin, AI Barricade Placement, What-If Simulator, Event Similarity Engine, Cost Optimisation Engine) are documented in the Glossary for vision purposes only and are explicitly **out of scope** for implementation.

---

## Glossary

- **Aegis**: The full Aegis Event Congestion Command System, encompassing the FastAPI backend and Next.js frontend.
- **RecommendationEngine**: The backend component (currently `recommendation_service.py`) responsible for generating officer, barricade, diversion, and signal recommendations.
- **RecommendationBuilder**: The new class introduced in Phase 1 that encapsulates the three-step scoring formula: `BaseScore`, `Modifier`, and `Final = Base + Modifier`.
- **ReasoningTree**: A structured JSON object attached to every recommendation response that records the intermediate calculation steps (base score, each modifier with its label and delta, and the final result) in a machine-readable and human-readable format.
- **PredictionTransparency**: The existing Pydantic schema in `prediction_schema.py` that records raw model output, calibration applied, and calibration source. Phase 1 extends this to include a `reasoning_tree` field.
- **JunctionRegistry**: A new database table (or query abstraction) that stores validated road-network junction nodes keyed by corridor. Used by the spatial barricade engine to query junctions within a 2 km radius of an event location.
- **SpatialEngine**: The backend component responsible for querying the JunctionRegistry and the Valhalla routing service to produce spatially-valid barricade positions and diversion polylines.
- **Valhalla**: The open-source routing engine (already integrated via `VALHALLA_URL` in `recommendation_service.py`) that accepts `avoid_locations` to produce road-closure-aware diversion routes.
- **UnifiedStore**: A Zustand store on the frontend that aggregates `LivePredictions`, `ActiveRecommendations`, and `HistoricalOutcomes` into a single reactive state container, replacing the current scattered `useState` calls in `Dashboard.tsx`.
- **HeatLayer**: A `react-leaflet-heat` overlay that renders predicted congestion scores as a weighted heat map on the Leaflet map.
- **CongestionScore**: A float value derived from `predicted_disruption_class` (Low → 0.25, Medium → 0.5, High → 0.75, Critical → 1.0) used as the weight for the HeatLayer.
- **PercentageError**: The learning-loop accuracy metric defined as `|Predicted − Actual| / Actual × 100`. Replaces mean-absolute-error as the primary dashboard-facing metric.
- **DisruptionClass**: One of four string values — `"Low"`, `"Medium"`, `"High"`, `"Critical"` — produced by the severity model.
- **Corridor**: A named geographic zone in Bengaluru (e.g., "Mysore Road", "Hosur Road") used as a bucketing key throughout the system.
- **BiasCorrection**: The signed float offset stored in `recalibration_log` that is added to a raw duration prediction to produce a calibrated output.
- **OSMCache**: The JSON file at `data/processed/osm_cache.json` that stores pre-fetched junctions, routes, and signals per corridor.
- **seed_vrp_data.py**: A new seed script that injects Worst Case, Average Case, and Best Case scenario events and outcomes into the database for verification and demo purposes.
- **Phase 2 (Out of Scope)**: Digital Twin Simulation (SUMO/MATSim), AI Barricade Placement, What-If Simulator, Event Similarity Engine, Cost Optimisation Engine.

---

## Requirements

### Requirement 1: Structured Reasoning Tree for Resource Recommendations

**User Story:** As a traffic operations officer, I want to see a step-by-step explanation of how the recommended officer count and barricade count were calculated, so that I can verify the logic and justify deployment decisions to my supervisor.

#### Acceptance Criteria

1. THE RecommendationBuilder SHALL compute officer count using the formula: `Final = BaseScore + sum(Modifiers)`, where `BaseScore` is looked up from `BASE_OFFICERS_LOOKUP` by `DisruptionClass` and `Modifiers` is a list of labelled integer deltas (e.g., `{"label": "road_closure", "delta": 2}`).
2. WHEN the RecommendationEngine generates a recommendation, THE RecommendationBuilder SHALL attach a `reasoning_tree` JSON object to the response containing: the `disruption_class` used, the `base_score` integer, the ordered list of `modifiers` (each with `label` and `delta`), and the `final_score` integer.
3. THE `reasoning_tree` attached to every recommendation response SHALL satisfy: `base_score + sum(modifiers[*].delta) == final_score` (arithmetic balance invariant).
4. WHEN a recommendation is generated for an event with `requires_road_closure = True`, THE RecommendationBuilder SHALL include a modifier entry with `label = "road_closure"` and `delta = 2` in the `reasoning_tree`.
5. WHEN a recommendation is generated for an event with `event_cause` in `{"public_event", "procession", "vip_movement"}`, THE RecommendationBuilder SHALL include a modifier entry with `label = "crowd_control"` and `delta = 1` in the `reasoning_tree`.
6. WHEN a recommendation is generated for an event that does not require road closure and is not a crowd-control cause, THE RecommendationBuilder SHALL produce a `reasoning_tree` with an empty `modifiers` list and `final_score` equal to `base_score`.
7. WHEN a recommendation is successfully generated, THE PredictionTransparency schema SHALL include a `reasoning_tree` field of type `dict` containing the ReasoningTree object; WHEN generation fails, the field SHALL be absent from the response.
8. IF the `DisruptionClass` received by the RecommendationBuilder is `None` or not in `{"Low", "Medium", "High", "Critical"}`, THEN THE RecommendationBuilder SHALL default to `"Medium"`, set `disruption_class` in the `reasoning_tree` to `"Medium"`, and include a modifier entry with `label = "fallback_class"` and `delta = 0`.
9. THE RecommendationBuilder SHALL compute barricade count using the same three-step formula and attach a separate `barricade_reasoning_tree` to the response with its own `base_score`, `modifiers`, and `final_score` satisfying the same arithmetic balance invariant.

---

### Requirement 2: Graph-Based Barricade Placement via Junction Registry

**User Story:** As a traffic operations officer, I want barricade recommendations to be restricted to topologically valid junctions on the real road network, so that I never receive a suggestion to place a barricade at an invalid or residential location.

#### Acceptance Criteria

1. THE SpatialEngine SHALL define a `JunctionRegistry` that stores junction nodes per corridor, where each node has: `junction_id` (string), `lat` (float), `lng` (float), `road_class` (one of: `"primary"`, `"secondary"`, `"tertiary"`, `"trunk"`, `"residential"`), and `corridor` (string).
2. WHEN `requires_road_closure` is `True` for an event, THE SpatialEngine SHALL query the JunctionRegistry for all junctions within a 2 km Haversine radius of `event_lat` / `event_lng`.
3. IF `requires_road_closure` is absent or `None` for an event, THEN THE SpatialEngine SHALL treat it as `False` and return an empty barricade list without raising an exception.
4. THE SpatialEngine SHALL exclude all junctions with `road_class = "residential"` from barricade candidates, regardless of proximity (safety invariant: no barricade on a residential road).
5. WHEN candidate junctions remain after road-class filtering, THE SpatialEngine SHALL rank them by ascending Haversine distance and return the top-N junctions, where N is determined by `BARRICADE_COUNT_BY_CLASS[disruption_class]`.
6. IF `disruption_class` is not a key in `BARRICADE_COUNT_BY_CLASS`, THEN THE SpatialEngine SHALL default N to `2` and SHALL NOT raise a `KeyError`.
7. WHEN barricade recommendations are returned by the API, every `lat`/`lng` coordinate pair SHALL correspond to a node that exists in the JunctionRegistry for the queried corridor; if a coordinate is not in the registry THE SpatialEngine SHALL log an error and exclude that coordinate from the response.
8. IF no valid junctions exist within the 2 km radius after road-class filtering, THEN THE SpatialEngine SHALL return an empty barricade list and SHALL NOT raise an unhandled exception.
9. WHEN the OSMCache is populated for a corridor, THE SpatialEngine SHALL load junction data from the OSMCache into the JunctionRegistry without making live Overpass API calls at request time.

---

### Requirement 3: Live Valhalla Diversion Routing with Avoidance

**User Story:** As a traffic operations officer, I want diversion routes to dynamically avoid the event location when a road closure is required, so that the suggested polylines route traffic around the blocked area rather than through it.

#### Acceptance Criteria

1. WHEN `requires_road_closure` is `True` for an event, THE SpatialEngine SHALL pass `event_lat` and `event_lng` wrapped in an `avoid_locations` array (with `radius = 50`) to the Valhalla routing service.
2. WHEN Valhalla returns a response with a non-empty geometry (at least 2 coordinate pairs), THE SpatialEngine SHALL decode the route polyline and return it as a list of `[lat, lng]` coordinate pairs in the `recommended_diversions` field.
3. WHEN the Valhalla service does not respond within 5 seconds or returns a non-200 HTTP status code, THE SpatialEngine SHALL fall back to the cached OSM routes for the corridor; IF the OSM cache is also empty, THE SpatialEngine SHALL return an empty `recommended_diversions` list; in both cases it SHALL log a warning including the HTTP status code or exception message.
4. THE `recommended_diversions` field in every recommendation response SHALL contain only coordinate pairs where latitude is in `[-90, 90]` and longitude is in `[-180, 180]`; any out-of-bounds pair SHALL be filtered out before the response is returned.
5. WHEN `requires_road_closure` is `False`, THE SpatialEngine SHALL use cached OSM routes only and SHALL NOT call the Valhalla service; IF the OSM cache is empty, it SHALL return an empty `recommended_diversions` list.
6. THE SpatialEngine SHALL apply a 50-metre avoidance radius around the event location when constructing the Valhalla `avoid_locations` payload.
7. THE SpatialEngine SHALL enforce a 5-second timeout on all Valhalla HTTP requests to make the unavailability condition in criterion 3 deterministic.

---

### Requirement 4: Centralised Frontend State Store (UnifiedStore)

**User Story:** As a frontend developer, I want a single reactive store that holds all live predictions, active recommendations, and historical outcomes, so that any component can subscribe to changes without prop-drilling or duplicated fetch logic.

#### Acceptance Criteria

1. THE UnifiedStore SHALL be implemented using Zustand and SHALL expose: `livePredictions` (map of `event_id → Prediction`), `activeRecommendations` (map of `event_id → Recommendation`), and `historicalOutcomes` (list of `Outcome` ordered newest-first), all initialised to empty collections.
2. WHEN the operator selects an event, THE UnifiedStore SHALL trigger fetch actions for `getPrediction` and `getRecommendation` in parallel; if one fetch fails the successful slice SHALL still update and `lastError` SHALL record only the failing action's error.
3. WHEN an outcome is submitted via the OutcomeForm, THE UnifiedStore SHALL prepend the new `Outcome` to `historicalOutcomes` and trigger a silent re-fetch; if the re-fetch fails, `historicalOutcomes` SHALL retain the newly prepended outcome.
4. WHILE the UnifiedStore is fetching data, THE Dashboard SHALL display a loading indicator scoped to the right-hand panel that disappears within 500 ms of the last fetch resolving, without hiding the event list or the map.
5. THE UnifiedStore SHALL expose a `selectedEventId` field (initially `null`) and a `setSelectedEvent(eventId: string | null)` action; calling `setSelectedEvent(null)` SHALL clear `selectedEventId` and stale slice entries for the previously selected event.
6. IF a fetch action fails, THEN THE UnifiedStore SHALL overwrite `lastError` with the error message and leave the affected slice in its last valid state.
7. WHERE the application is running in mock mode (`NEXT_PUBLIC_MOCK_MODE=true`), THE UnifiedStore SHALL use the existing mock data functions in `lib/api.ts` rather than making network requests.
8. WHEN `setSelectedEvent` is called with a new `eventId`, THE UnifiedStore SHALL clear the `livePredictions` and `activeRecommendations` entries for the previous event before initiating fetches for the new event.

---

### Requirement 5: Percentage-Error Metric in the Learning Loop

**User Story:** As a data analyst, I want the learning report to show percentage error alongside absolute error, so that I can compare model accuracy across corridors with very different baseline durations.

#### Acceptance Criteria

1. THE LearningReport endpoint SHALL compute `PercentageError = |predicted_duration_min − actual_duration_min| / actual_duration_min × 100` for each outcome where both fields are non-null; the corrected variant SHALL use `raw_pred = stored_prediction − active_bias` in place of `predicted_duration_min`.
2. THE LearningReport endpoint SHALL include `mean_percentage_error` and `mean_corrected_percentage_error` (both floats) in the top-level response body alongside the existing error fields.
3. WHEN `actual_duration_min` is zero or negative for an outcome, THE LearningReport endpoint SHALL exclude that outcome from both the numerator and denominator and SHALL NOT raise a division-by-zero exception.
4. THE per-bucket breakdown in the LearningReport response SHALL include `mean_percentage_error` and `mean_corrected_percentage_error` per bucket.
5. IF fewer than 3 valid (non-zero actual) outcomes exist for a bucket, THEN THE LearningReport endpoint SHALL return `null` for `mean_corrected_percentage_error` in that bucket rather than a potentially misleading value.
6. WHEN a learning report response includes at least one bucket with N ≥ 3 valid outcomes, `mean_corrected_percentage_error` for that bucket SHALL be ≤ `mean_percentage_error` (learning convergence invariant — enforceable as a regression gate after sufficient recalibration data).

---

### Requirement 6: Interactive Congestion Heatmap

**User Story:** As a traffic operations officer, I want to see a heat map overlay on the Bengaluru road map that shows predicted congestion intensity by location, so that I can visually identify high-risk corridors at a glance.

#### Acceptance Criteria

1. THE MapView component SHALL render a heat map overlay using a heat-map library (such as `react-leaflet-heat`) as a Leaflet layer on top of the existing `MapContainer`.
2. THE HeatLayer SHALL convert each event's `predicted_disruption_class` to a weight: `Low → 0.25`, `Medium → 0.5`, `High → 0.75`, `Critical → 1.0`, using the event's `latitude` and `longitude` as the heat point location.
3. WHEN the operator selects an event, THE HeatLayer SHALL update to reflect the predictions for the currently loaded events within 500 ms, without requiring a full page reload.
4. THE HeatLayer SHALL render at a Leaflet pane z-index strictly lower than the pane used for diversion Polylines, ensuring diversion polylines are always rendered on top of the heat gradient.
5. IF `livePredictions` is empty in the UnifiedStore, THEN THE HeatLayer SHALL render with zero heat points and SHALL NOT throw a runtime error.
6. WHERE the `predicted_disruption_class` for an event is `null` or undefined, THE HeatLayer SHALL omit that event from the heat-point array.
7. THE HeatLayer SHALL use a fixed radius of 25 pixels and a blur of 15 pixels as default rendering parameters, configurable via component props.

---

### Requirement 7: Seed Data Script for Verification Scenarios

**User Story:** As a developer, I want a seed script that injects Worst Case, Average Case, and Best Case scenario data into the database, so that I can verify all four Phase 1 features end-to-end without relying on production data.

#### Acceptance Criteria

1. THE seed_vrp_data.py script SHALL insert three named scenario groups: `"worst_case"` (Critical disruption, road closure required, cause `public_event`), `"average_case"` (Medium disruption, no closure, cause `vehicle_breakdown`), and `"best_case"` (Low disruption, no closure, cause `construction`).
2. WHEN the seed script is executed, it SHALL use `INSERT … ON CONFLICT DO NOTHING` so that running it twice does not insert duplicate rows and exits with a zero return code both times.
3. THE seed_vrp_data.py script SHALL insert at least one outcome per scenario with non-null `actual_duration_min` and `predicted_duration_min` values so that the LearningReport endpoint has data to operate on.
4. WHEN the seed script completes, it SHALL print per-scenario output to stdout in the format: `[scenario] events: X inserted, Y skipped | outcomes: A inserted, B skipped`.
5. WHEN the seed script is run against an empty database, it SHALL complete without error and a subsequent `GET /learning_report` request SHALL return a response with a non-empty `per_bucket_breakdown` array.

---

### Requirement 8: Visual Regression Gate — Heatmap Does Not Obstruct Diversion Polylines

**User Story:** As a traffic operations officer, I want diversion polylines to always be visible above the heat map layer, so that routing guidance is never hidden by congestion shading.

#### Acceptance Criteria

1. WHEN both a HeatLayer and at least one diversion Polyline are rendered on the map simultaneously, the diversion Polyline SHALL be visually rendered above the heat map gradient — the Polyline SHALL NOT be covered or hidden by any part of the heat overlay.
2. WHEN both a HeatLayer and at least one diversion Polyline are present on the map simultaneously, THE MapView component SHALL render without any React or Leaflet console errors, and the Polyline SHALL remain fully opaque and clickable.
3. THE MapView component SHALL expose a `showHeatmap` boolean prop (default `true`) that, when set to `false`, suppresses the HeatLayer entirely without affecting barricade markers, signal markers, or diversion polylines.
4. IF the heat-map layer fails to initialise (e.g., the library throws during mount), THEN THE MapView component SHALL catch the error via an error boundary, render the map without the HeatLayer, and display no uncaught console exception.

---

### Requirement 9: Contract-First JSON Output Definitions

**User Story:** As a developer, I want the JSON contracts for the Impact Score, Resource Engine, and recommendation outputs to be formally defined before any logic is written, so that backend and frontend can be developed in parallel against a stable interface.

#### Acceptance Criteria

1. THE RecommendationEngine SHALL produce responses conforming to the following contract for `reasoning_tree` and `barricade_reasoning_tree`, where `base_score` and `final_score` are non-negative integers and `modifiers` contains at most 3 entries:
   ```json
   {
     "disruption_class": "string (Low|Medium|High|Critical)",
     "base_score": "non-negative integer",
     "modifiers": [{ "label": "string", "delta": "integer" }],
     "final_score": "non-negative integer"
   }
   ```
2. THE LearningReport endpoint SHALL produce responses conforming to the following complete contract:
   ```json
   {
     "total_outcomes_logged": "integer",
     "mean_raw_error": "float",
     "mean_corrected_error": "float",
     "mean_percentage_error": "float | null",
     "mean_corrected_percentage_error": "float | null",
     "improvement_pct": "float",
     "severity_raw_accuracy": "float",
     "per_bucket_breakdown": [{
       "event_cause": "string",
       "corridor": "string",
       "n_outcomes": "integer",
       "mean_raw_error": "float",
       "mean_corrected_error": "float",
       "mean_percentage_error": "float | null",
       "mean_corrected_percentage_error": "float | null"
     }]
   }
   ```
3. THE HeatLayer data format SHALL conform to the following array contract, where `lat` ∈ `[-90, 90]`, `lng` ∈ `[-180, 180]`, and `weight` ∈ `[0.0, 1.0]`; an empty array is valid:
   ```json
   [{ "lat": "float", "lng": "float", "weight": "float (0.0–1.0)" }]
   ```
4. THE FastAPI application SHALL declare a `response_model` on every endpoint covered by criteria 1 and 2; WHEN a response value is missing a required field or has a wrong type, Pydantic SHALL reject it and FastAPI SHALL return HTTP 422 rather than HTTP 500.

---

## Phase 2 Vision (Out of Scope for Phase 1 Implementation)

The following capabilities are documented for roadmap visibility only. They SHALL NOT be implemented in Phase 1:

- **Digital Twin Simulation**: SUMO / MATSim integration to simulate traffic flow under event conditions.
- **AI Barricade Placement**: Graph optimisation to minimise total traffic delay across the road network.
- **What-If Simulator**: Scenario sandbox allowing operators to test hypothetical event configurations.
- **Event Similarity Engine**: KNN / vector-embedding search for semantically similar historical events.
- **Cost Optimisation Engine**: Multi-objective optimisation minimising officers deployed, barricades placed, and total vehicle delay cost.
