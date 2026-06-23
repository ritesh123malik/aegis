# Implementation Plan: Aegis Core Intelligence — Phase 1

## Overview

Four parallel tracks implement the Phase 1 capabilities: Track A (Backend Foundation) must land first as it unblocks all other tracks. Track B (Learning Report) depends on A1 schemas. Track C (Frontend) depends on A1 type contracts. Track D (Verification) depends on the completed A, B, and C implementations.

All backend code is Python (FastAPI/SQLAlchemy/Pydantic v2). All frontend code is TypeScript (Next.js 14/React 18/Zustand/react-leaflet). Property-based tests use `hypothesis` (backend) and `fast-check` (frontend).

---

## Tasks

### Track A — Backend Foundation

- [ ] 1. Define Pydantic response schemas and wire `response_model` to endpoints
  - [ ] 1.1 Create `backend/app/schemas/recommendation_schema.py` with all new types
    - Add `ModifierEntrySchema(BaseModel)`: `label: str`, `delta: int`
    - Add `ReasoningTreeSchema(BaseModel)` with fields `disruption_class`, `base_score`, `modifiers`, `final_score` and a `@model_validator(mode="after")` that asserts `base_score + sum(m.delta for m in modifiers) == final_score`; raise `ValueError` on imbalance
    - Add `JunctionNode(BaseModel)`: `junction_id`, `lat`, `lng`, `road_class`, `corridor`
    - Add `DiversionRoute(BaseModel)`: `polyline: list[list[float]]`, `description: str`
    - Add `SignalAttention(BaseModel)`: `lat`, `lng`, `signal_id`, `recommended_action`
    - Add `BaselineComparison(BaseModel)`: `naive_baseline_officers`, `our_recommendation_officers`, `adjustment_breakdown`, `baseline_source`
    - Add `RecommendationResponse(BaseModel)` with all seven fields including `reasoning_tree` and `barricade_reasoning_tree` of type `ReasoningTreeSchema`
    - Export all new types from `backend/app/schemas/__init__.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.9, 9.1, 9.4_

  - [ ] 1.2 Create `backend/app/schemas/learning_report_schema.py` with `BucketBreakdown` and `LearningReportResponse`
    - `BucketBreakdown(BaseModel)`: `event_cause: str`, `corridor: str`, `n_outcomes: int`, `mean_raw_error: float`, `mean_corrected_error: float`, `mean_percentage_error: Optional[float]`, `mean_corrected_percentage_error: Optional[float]`
    - `LearningReportResponse(BaseModel)`: all seven top-level fields matching the contract in Requirement 9.2; `mean_percentage_error` and `mean_corrected_percentage_error` are `Optional[float]`
    - _Requirements: 5.1, 5.2, 5.4, 9.2, 9.4_

  - [ ] 1.3 Annotate `GET /recommend/{event_id}` with `response_model=RecommendationResponse`
    - In `backend/app/routers/recommend.py`, add `response_model=RecommendationResponse` to the `@router.get` decorator
    - Import `RecommendationResponse` from the new schemas module
    - Do not change any business logic in this task — only the decorator annotation
    - _Requirements: 9.4_

  - [ ] 1.4 Annotate `GET /learning_report` with `response_model=LearningReportResponse`
    - In `backend/app/routers/learning_report.py`, add `response_model=LearningReportResponse` to the `@router.get` decorator
    - Import `LearningReportResponse` from the new schemas module
    - Do not change any business logic in this task — only the decorator annotation
    - _Requirements: 9.4_

  - [ ]* 1.5 Write unit tests for schema arithmetic validator
    - In `backend/tests/test_recommendation_schema.py`, assert that `ReasoningTreeSchema` raises `ValueError` when `base_score + sum(deltas) != final_score`
    - Assert valid trees (balanced arithmetic) instantiate without error
    - Assert `BucketBreakdown` and `LearningReportResponse` accept `None` for optional percentage fields
    - _Requirements: 1.3, 9.1_

- [ ] 2. Implement `JunctionRegistry` DB model and Alembic migration, then populate from OSMCache
  - [ ] 2.1 Add `JunctionRegistry` SQLAlchemy model in `backend/app/models/junction_registry.py`
    - Column definitions: `junction_id TEXT PRIMARY KEY`, `corridor TEXT NOT NULL`, `lat FLOAT NOT NULL`, `lng FLOAT NOT NULL`, `road_class TEXT NOT NULL`, `created_at TIMESTAMPTZ server_default=now()`
    - Add `CheckConstraint` on `road_class IN ('primary','secondary','tertiary','trunk','residential')`
    - Add `index=True` on `corridor` column
    - Register the model in `backend/app/models/__init__.py`
    - _Requirements: 2.1_

  - [ ] 2.2 Write Alembic migration to create `junction_registry` table
    - Create `alembic/versions/<hash>_add_junction_registry.py` with `upgrade()` calling `op.create_table(...)` and `op.create_index('idx_junction_registry_corridor', 'junction_registry', ['corridor'])`
    - `downgrade()` drops index then table
    - Set `down_revision` to `'aecd859853d9'` (latest existing migration)
    - _Requirements: 2.1_

  - [ ] 2.3 Implement `OSMCache` loader in `backend/app/services/osm_service.py`
    - Add `load_junctions_into_registry(db: Session) -> int` function: reads `data/processed/osm_cache.json`, iterates every corridor's `junctions` list, bulk-upserts rows into `junction_registry` using `INSERT … ON CONFLICT (junction_id) DO NOTHING`, returns count of inserted rows
    - Keep all existing cached-read functions untouched
    - _Requirements: 2.1, 2.9_

  - [ ]* 2.4 Write unit tests for OSMCache loader
    - Use an in-memory SQLite session to verify rows are inserted on first call and skipped on second (idempotence)
    - _Requirements: 2.9_


- [ ] 3. Implement `RecommendationBuilder` class in `recommendation_service.py`
  - [ ] 3.1 Add `RecommendationBuilder` dataclass and both tree-building methods
    - Define `@dataclass class ModifierEntry: label: str; delta: int`
    - Define `@dataclass class ReasoningTree: disruption_class: str; base_score: int; modifiers: list[ModifierEntry]; final_score: int` — compute `final_score` as `base_score + sum(m.delta for m in modifiers)` inside the builder, never store it independently
    - `build_officer_tree(disruption_class, requires_road_closure, event_cause) -> ReasoningTree`: replicate the existing `calculate_officer_count` logic but emit a `ModifierEntry` for each non-zero adjustment; if `disruption_class` is `None` or unknown default to `"Medium"` and prepend a `ModifierEntry(label="fallback_class", delta=0)`
    - `build_barricade_tree(disruption_class) -> ReasoningTree`: lookup `BARRICADE_COUNT_BY_CLASS`, apply same `None`/unknown fallback; `modifiers` list is empty when no adjustments apply
    - Keep existing `calculate_officer_count` and related functions intact for backward compatibility; the builder is additive
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.8, 1.9_

  - [ ] 3.2 Wire `RecommendationBuilder` output into `generate_recommendation` return value
    - Instantiate `RecommendationBuilder` inside `generate_recommendation`
    - Call `build_officer_tree` and `build_barricade_tree`, convert each `ReasoningTree` to `dict` via `dataclasses.asdict`
    - Add `reasoning_tree` and `barricade_reasoning_tree` keys to the returned dict
    - _Requirements: 1.2, 1.7_

  - [ ]* 3.3 Write property test for arithmetic balance invariant (Property 1)
    - **Property 1: Arithmetic Balance Invariant**
    - **Validates: Requirements 1.1, 1.3, 1.9**
    - File: `backend/tests/test_recommendation_builder.py`
    - Use `@given(disruption_class=st.sampled_from(["Low","Medium","High","Critical",None,"INVALID"]), requires_road_closure=st.booleans(), event_cause=st.text(min_size=1, max_size=40))`
    - Assert `officer_tree.base_score + sum(m.delta for m in officer_tree.modifiers) == officer_tree.final_score` and same for barricade tree

- [ ] 4. Implement `SpatialEngine` service
  - [ ] 4.1 Create `backend/app/services/spatial_engine.py` with `SpatialEngine` class
    - `query_barricade_candidates(corridor, event_lat, event_lon, disruption_class, requires_road_closure, db: Session) -> list[JunctionNode]`:
      - If `requires_road_closure` is `False` or `None`, return `[]` immediately
      - Query `junction_registry` WHERE `corridor = :corridor`, compute Haversine distance for each row, keep only rows ≤ 2.0 km, exclude `road_class = "residential"`, sort ascending by distance, return top-N via `BARRICADE_COUNT_BY_CLASS.get(disruption_class, 2)`
      - Return typed `JunctionNode` instances (importable from the new schemas)
    - `query_barricade_candidates_from_list(event_lat, event_lon, junctions, disruption_class, requires_road_closure) -> list[JunctionNode]`:
      - Pure-function variant (no DB) operating on an in-memory list — used by property tests
    - `get_diversion_routes(corridor, event_lat, event_lon, requires_road_closure) -> list[DiversionRoute]`:
      - If `requires_road_closure=True` call Valhalla with `avoid_locations=[{lat, lon, radius:50}]` and 5 s timeout; on timeout or non-200, log warning and fall back to `get_cached_routes(corridor)`
      - If `requires_road_closure=False`, use OSM cache only
      - After obtaining coordinate list, call `filter_valid_coordinates` to strip any pair outside `lat∈[-90,90]` or `lng∈[-180,180]`
      - If cache is also empty after Valhalla failure, return `[]`
    - Add top-level `filter_valid_coordinates(coords: list[tuple[float,float]]) -> list[tuple[float,float]]` helper in the same file
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 4.2 Replace the barricade and diversion calls in `recommend.py` router to use `SpatialEngine`
    - Instantiate `SpatialEngine` in `get_recommendation`
    - Replace `get_barricade_locations(...)` call with `spatial_engine.query_barricade_candidates(..., db=db)`
    - Replace the inline Valhalla + diversion block with `spatial_engine.get_diversion_routes(...)`
    - _Requirements: 2.2, 3.1, 3.5_

  - [ ]* 4.3 Write property test for spatial radius and safety filter (Property 2)
    - **Property 2: Spatial Radius and Safety Filter**
    - **Validates: Requirements 2.2, 2.4, 2.5, 2.7**
    - File: `backend/tests/test_spatial_engine.py`
    - Use `@given(event_coords=coordinate_strategy(), junctions=st.lists(junction_strategy(), min_size=0, max_size=50), disruption_class=st.sampled_from([...]))`
    - Call `SpatialEngine().query_barricade_candidates_from_list(...)` and assert: every result has Haversine ≤ 2.0 km, no result has `road_class = "residential"`, distances are in ascending order

  - [ ]* 4.4 Write property test for coordinate bounds filter (Property 3)
    - **Property 3: Coordinate Bounds Filter**
    - **Validates: Requirements 3.4, 9.3**
    - File: `backend/tests/test_spatial_engine.py`
    - Use `@given(coords=st.lists(st.tuples(st.floats(-200,200), st.floats(-200,200)), min_size=0, max_size=100))`
    - Call `filter_valid_coordinates(coords)` and assert every returned pair satisfies `lat∈[-90,90]` and `lng∈[-180,180]`

- [ ] 5. Checkpoint A — ensure all backend foundation tests pass
  - Ensure all tests pass, ask the user if questions arise.


### Track B — Learning Report Extension

- [ ] 6. Extend `learning_report.py` with `PercentageError` computation
  - [ ] 6.1 Add `compute_percentage_error(predicted: float, actual: float) -> float` helper in `learning_report.py`
    - Formula: `abs(predicted - actual) / actual * 100`
    - Caller is responsible for guarding `actual > 0`; this function assumes a valid non-zero denominator
    - _Requirements: 5.1_

  - [ ] 6.2 Extend the outcome-processing loop to compute percentage errors
    - Before computing `raw_err` / `corrected_err`, skip the outcome entirely if `outcome.actual_duration_min <= 0` (no division-by-zero)
    - Compute `raw_pct = compute_percentage_error(raw_pred, actual)` and `corrected_pct = compute_percentage_error(pred.predicted_duration_min, actual)`
    - Accumulate per-bucket percentage-error lists alongside the existing MAE lists
    - _Requirements: 5.1, 5.3_

  - [ ] 6.3 Aggregate top-level and per-bucket percentage-error means, apply null-for-small-N rule
    - Top-level `mean_percentage_error`: average of all `raw_pct` values (None if no valid outcomes)
    - Top-level `mean_corrected_percentage_error`: average of all `corrected_pct` values (None if no valid outcomes)
    - Per-bucket: compute bucket means; set `mean_corrected_percentage_error = None` for buckets where `n_valid < 3`
    - Update the returned dict to include all four new keys (two top-level, two per-bucket) matching the `LearningReportResponse` schema
    - _Requirements: 5.2, 5.4, 5.5_

  - [ ]* 6.4 Write property test for percentage-error arithmetic (Property 4)
    - **Property 4: Percentage-Error Arithmetic Correctness**
    - **Validates: Requirements 5.1, 5.3**
    - File: `backend/tests/test_learning_report.py`
    - Use `@given(predicted=st.floats(min_value=0.1,max_value=1000.0), actual=st.floats(min_value=0.1,max_value=1000.0), bias=st.floats(min_value=-100.0,max_value=100.0))`
    - Assert `compute_percentage_error(predicted, actual)` equals `abs(predicted-actual)/actual*100` within `rel_tol=1e-9`
    - Assert corrected variant uses `predicted - bias` as the numerand

  - [ ]* 6.5 Write property test for learning convergence invariant (Property 5)
    - **Property 5: Learning Convergence Invariant**
    - **Validates: Requirements 5.6**
    - File: `backend/tests/test_learning_report.py`
    - Use `@given(outcomes=st.lists(outcome_with_bias_strategy(), min_size=3, max_size=50))`
    - Call a `compute_bucket_errors(outcomes)` helper that returns `(mean_raw, mean_corrected)` and assert `mean_corrected <= mean_raw + 1e-9`


### Track C — Frontend

- [ ] 7. Implement `UnifiedStore` in `frontend/lib/store.ts`
  - [ ] 7.1 Install `zustand` and add TypeScript types for store shapes
    - Add `zustand@^4.5.0` to `frontend/package.json` dependencies
    - Add `fast-check@^3.15.0` to `devDependencies` (needed for property tests in task 11)
    - Create type declarations in `frontend/lib/types.ts`: `Prediction`, `Recommendation`, `Outcome`, `OutcomeInput` — aligned with the Pydantic schemas from task 1
    - _Requirements: 4.1_

  - [ ] 7.2 Create `frontend/lib/store.ts` with the three state slices and all actions
    - Implement `livePredictions: Record<string, Prediction>` slice (initially `{}`)
    - Implement `activeRecommendations: Record<string, Recommendation>` slice (initially `{}`)
    - Implement `historicalOutcomes: Outcome[]` slice (initially `[]`, newest-first ordering)
    - Implement `selectedEventId: string | null` and `loading: boolean` and `lastError: string | null`
    - Implement `setSelectedEvent(eventId)`: clears stale entries for previous `selectedEventId` from both maps before updating `selectedEventId`
    - Implement `fetchPredictionAndRecommendation(eventId)`: fires `getPrediction` and `getRecommendation` in parallel via `Promise.allSettled`; successful slices update independently; failures set `lastError` without touching the successful slice
    - Implement `submitOutcome(eventId, data)`: prepend new outcome to `historicalOutcomes`, then trigger silent re-fetch; if re-fetch fails, retain the prepended outcome and set `lastError`
    - When `NEXT_PUBLIC_MOCK_MODE=true`, import mock functions from `lib/api.ts` instead of making fetch calls
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.7, 4.8_

  - [ ]* 7.3 Write unit tests for UnifiedStore
    - Test `setSelectedEvent(null)` clears stale prediction and recommendation entries
    - Test that a rejected `getRecommendation` does not prevent `livePredictions` from updating
    - Test `submitOutcome` prepends even when the re-fetch rejects
    - _Requirements: 4.2, 4.3, 4.5, 4.8_

- [ ] 8. Migrate `Dashboard.tsx` to use `UnifiedStore`
  - [ ] 8.1 Replace `useState` prediction/recommendation state with `useUnifiedStore` subscriptions
    - Remove local `useState` declarations for `prediction`, `recommendation`, `loading`, `error`
    - Subscribe to `livePredictions[selectedEventId]`, `activeRecommendations[selectedEventId]`, `loading`, `lastError` from the store
    - Replace manual `fetch` calls with `store.fetchPredictionAndRecommendation(eventId)`
    - Replace manual `setSelectedEventId` calls with `store.setSelectedEvent(eventId)`
    - Pass `store.submitOutcome` to `OutcomeForm`
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ] 8.2 Add scoped loading indicator that disappears ≤ 500 ms after fetch completes
    - Render the loading spinner only inside the right-hand panel (`PredictionPanel` + `RecommendationPanel` area), not over the event list or the map
    - The spinner reads from `store.loading`
    - Add a CSS transition so it fades out; ensure it is invisible within 500 ms of `loading` flipping to `false`
    - _Requirements: 4.4_

  - [ ] 8.3 Add error display for `lastError` below the right-hand panel header
    - Render a dismissable error banner when `store.lastError` is non-null
    - Calling `store.setSelectedEvent(newId)` clears the banner for the new selection
    - _Requirements: 4.6_


- [ ] 9. Add `HeatLayer` and visual-regression safeguards to `MapView.tsx`
  - [ ] 9.1 Install `react-leaflet-heat` and wire into `MapView.tsx`
    - Add `react-leaflet-heat@^0.1.2` (or latest) and `@types/leaflet.heat` to `frontend/package.json`
    - In `MapView.tsx`, create a `heatPane` Leaflet pane with `zIndex: 300` and a `diversionPane` pane with `zIndex: 400`
    - Add `const DISRUPTION_WEIGHT: Record<string, number> = { Low: 0.25, Medium: 0.5, High: 0.75, Critical: 1.0 }`
    - Add `function toHeatPoints(predictions: Record<string, Prediction>): HeatPoint[]`: filters entries with null/undefined `predicted_disruption_class`, maps each to `{lat, lng, weight: DISRUPTION_WEIGHT[...]}` using event latitude/longitude
    - Render `<HeatLayer points={toHeatPoints(livePredictions)} radius={25} blur={15} />` inside `heatPane`
    - Move existing `Polyline` diversion elements into `diversionPane`
    - Add a `showHeatmap: boolean` prop (default `true`) that conditionally renders the `HeatLayer`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 8.1, 8.3_

  - [ ] 9.2 Wrap `HeatLayer` in a React error boundary
    - Create `frontend/components/HeatLayerBoundary.tsx` — a class-based `React.Component` error boundary
    - `componentDidCatch` logs the error; `render` returns `null` when `hasError` is true so the map renders without the heat layer
    - Wrap the `HeatLayer` usage in `MapView.tsx` with `<HeatLayerBoundary>`
    - _Requirements: 8.4_

  - [ ]* 9.3 Write property test for DisruptionClass weight mapping (Property 6)
    - **Property 6: DisruptionClass Weight Mapping**
    - **Validates: Requirements 6.2, 6.6, 9.3**
    - File: `frontend/__tests__/toHeatPoints.test.ts`
    - Use `fast-check`: `fc.assert(fc.property(fc.record({predicted_disruption_class: fc.oneof(...), latitude: fc.float(...), longitude: fc.float(...)}), ...))`
    - Assert returned `weight` equals the expected mapping value, is in `[0.0, 1.0]`, and null/undefined class yields zero points
    - Run with `{ numRuns: 100 }`

  - [ ]* 9.4 Write visual regression tests for z-index ordering and `showHeatmap` prop
    - File: `frontend/__tests__/MapView.visual.test.tsx`
    - Use `@testing-library/react` to render `MapView` and assert `heatPane` container has `z-index: 300` lower than `diversionPane` `z-index: 400`
    - Assert `showHeatmap={false}` removes the `HeatLayer` canvas element from the DOM
    - Assert simulated Leaflet error boundary scenario renders the map wrapper without throwing
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 10. Checkpoint C — ensure all frontend tests pass
  - Ensure all tests pass, ask the user if questions arise.


### Track D — Verification

- [ ] 11. Create `seed_vrp_data.py` seed script
  - [ ] 11.1 Write scenario event and outcome insertions using `ON CONFLICT DO NOTHING`
    - Create `seed_vrp_data.py` at the project root
    - Define three scenario dicts: `worst_case` (Critical, `requires_road_closure=True`, cause `public_event`, realistic Bengaluru lat/lng, non-null `actual_duration_min` ≥ 1), `average_case` (Medium, no closure, cause `vehicle_breakdown`), `best_case` (Low, no closure, cause `construction`)
    - For events: `INSERT INTO events (...) VALUES (...) ON CONFLICT (event_id) DO NOTHING`; track inserted vs skipped counts by comparing row counts before/after
    - For outcomes: `INSERT INTO outcomes (...) VALUES (...) ON CONFLICT (outcome_id) DO NOTHING`; same count tracking
    - Print per-scenario line: `[scenario] events: X inserted, Y skipped | outcomes: A inserted, B skipped`
    - Always exit with code 0
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 11.2 Write property test for seed script idempotence (Property 7)
    - **Property 7: Seed Script Idempotence**
    - **Validates: Requirements 7.2**
    - File: `backend/tests/test_seed_idempotent.py`
    - Use a `tmp_db_session` fixture backed by an in-memory SQLite DB (or test PostgreSQL)
    - Run `run_seed_script(session)` twice; assert total `events` and `outcomes` row count is identical after both runs; assert exit code is 0 on both

- [ ] 12. Write integration tests for API contracts and Valhalla fallback
  - [ ] 12.1 Write `backend/tests/test_recommend_contract.py`
    - Use FastAPI `TestClient`; run `seed_vrp_data.py` fixtures first
    - GET `/recommend/{worst_case_event_id}` → assert HTTP 200, response body validates as `RecommendationResponse`, `reasoning_tree.base_score + sum(deltas) == reasoning_tree.final_score`
    - Assert HTTP 404 for an unknown event_id
    - Mock `generate_recommendation` to return a dict with a missing required field; assert FastAPI returns HTTP 422
    - _Requirements: 1.2, 1.3, 9.1, 9.4_

  - [ ] 12.2 Write `backend/tests/test_learning_report_contract.py`
    - GET `/learning_report` after seeding; assert HTTP 200 and all required fields present
    - Assert `mean_percentage_error` is `float` or `null`; assert `per_bucket_breakdown` is non-empty
    - Assert buckets with `n_outcomes < 3` have `mean_corrected_percentage_error = null`
    - _Requirements: 5.2, 5.4, 5.5, 9.2, 9.4_

  - [ ] 12.3 Write `backend/tests/test_valhalla_fallback.py`
    - Patch `requests.post` to raise `requests.exceptions.Timeout`
    - Call `spatial_engine.get_diversion_routes(corridor=..., requires_road_closure=True, ...)`
    - Assert response uses OSM cache routes (non-empty list from the preloaded `osm_cache.json`)
    - Assert a warning was logged containing the exception message
    - Patch `requests.post` to return HTTP 503; assert same OSM fallback behaviour
    - _Requirements: 3.3, 3.7_

  - [ ]* 12.4 Write visual regression gate tests
    - File: `frontend/__tests__/MapView.visual.test.tsx` (extend task 9.4)
    - Playwright or `@testing-library/react` snapshot: verify `heatPane` z-index 300 is present when `showHeatmap={true}`
    - Verify `diversionPane` z-index 400 is present simultaneously
    - Verify `heatPane` canvas is absent when `showHeatmap={false}`
    - _Requirements: 8.1, 8.2, 8.3_

- [ ] 13. Final checkpoint — ensure all tests pass end-to-end
  - Ensure all tests pass (backend pytest suite + frontend test suite), ask the user if questions arise.


---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; all property-based and unit test sub-tasks carry this mark.
- Track A (tasks 1–4) must be merged before starting Track B (task 6) or Track C (tasks 7–9).
- Track B and Track C can proceed in parallel once Track A is complete.
- Track D (tasks 11–12) requires all of A, B, and C to be stable.
- Property tests use `hypothesis==6.x` (backend) and `fast-check^3.15` (frontend); pin exact versions before installing.
- The `JunctionRegistry` table must be populated via `load_junctions_into_registry` before any integration test runs; this is the responsibility of the test fixture setup.
- Do not call the live Overpass API at request time; `osm_service.py` cached-read functions remain the only runtime path.

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "2.1", "2.2"] },
    { "id": 2, "tasks": ["1.5", "2.3", "3.1", "7.1"] },
    { "id": 3, "tasks": ["2.4", "3.2", "3.3", "6.1", "7.2"] },
    { "id": 4, "tasks": ["4.1", "6.2", "7.3", "8.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "4.4", "6.3", "8.2", "8.3"] },
    { "id": 6, "tasks": ["6.4", "6.5", "9.1"] },
    { "id": 7, "tasks": ["9.2", "9.3", "11.1"] },
    { "id": 8, "tasks": ["9.4", "11.2", "12.1", "12.2", "12.3"] },
    { "id": 9, "tasks": ["12.4"] }
  ]
}
```
