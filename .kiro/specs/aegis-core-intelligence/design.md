# Design Document: Aegis Core Intelligence — Phase 1

## Overview

Phase 1 adds four interconnected capabilities to the existing Aegis FastAPI/PostgreSQL/Next.js stack:

1. **Explainable Resource Engine** — `RecommendationBuilder` produces a structured `ReasoningTree` JSON for every officer and barricade count recommendation.
2. **Spatial Intelligence** — `JunctionRegistry` (new DB table) + `SpatialEngine` (service) ground barricade placement in the real road network; live Valhalla routing replaces static OSM cache for closure events.
3. **Historical Learning Dashboard** — Zustand `UnifiedStore` replaces scattered `useState` calls; `PercentageError` replaces MAE as the primary learning-loop metric.
4. **Interactive Congestion Heatmap** — `react-leaflet-heat` `HeatLayer` converts `DisruptionClass` to a [0,1] weight and renders below diversion Polylines.

Supporting additions: an idempotent `seed_vrp_data.py` seed script, a visual regression gate for z-index ordering, and contract-first Pydantic `response_model` declarations on all relevant endpoints.

---

## Architecture

The system follows the existing three-tier layout. Phase 1 touches each tier minimally and surgically.

```mermaid
graph TD
  subgraph Frontend [Next.js 14 — localhost:3000]
    US[UnifiedStore\nZustand]
    DV[Dashboard.tsx]
    MV[MapView.tsx\n+ HeatLayer]
    LP[learning-report.tsx]
    US --> DV
    US --> MV
    US --> LP
  end

  subgraph Backend [FastAPI — localhost:8000]
    RP[POST /predict\nresponse_model=PredictionResponse]
    RR[GET /recommend/{id}\nresponse_model=RecommendationResponse]
    LR[GET /learning_report\nresponse_model=LearningReportResponse]
    RB[RecommendationBuilder]
    SE[SpatialEngine]
    VH[Valhalla HTTP client\n5s timeout]
    RR --> RB
    RR --> SE
    SE --> VH
  end

  subgraph DB [PostgreSQL — localhost:5433]
    EV[(events)]
    PR[(predictions)]
    JR[(junction_registry)]
    OT[(outcomes)]
    RC[(recalibration_log)]
  end

  subgraph External
    OSM[(OSMCache\nosm_cache.json)]
    VAL[Valhalla\nlocalhost:8002]
  end

  DV -- POST /predict --> RP
  DV -- GET /recommend --> RR
  DV -- GET /learning_report --> LR
  SE --> JR
  SE --> OSM
  VH --> VAL
  RP --> PR
  RR --> EV
  LR --> OT
  LR --> RC
```

All new backend code lives inside the existing `backend/app/` package. No new top-level services are introduced.

---

## Components and Interfaces

### 2.1 RecommendationBuilder (backend)

**File:** `backend/app/services/recommendation_service.py`

Replaces the inline arithmetic in `calculate_officer_count` and `get_barricade_locations` with a class that also emits a `ReasoningTree`.

```python
@dataclass
class ModifierEntry:
    label: str
    delta: int

@dataclass
class ReasoningTree:
    disruption_class: str
    base_score: int
    modifiers: list[ModifierEntry]
    final_score: int
    # Invariant: base_score + sum(m.delta for m in modifiers) == final_score

class RecommendationBuilder:
    def build_officer_tree(self, disruption_class, requires_road_closure, event_cause) -> ReasoningTree
    def build_barricade_tree(self, disruption_class) -> ReasoningTree
```

Key design decisions:
- `disruption_class=None` or unknown value defaults to `"Medium"` and adds a `fallback_class` modifier with `delta=0`.
- Both trees are serialised to `dict` and attached to the recommendation response as `reasoning_tree` and `barricade_reasoning_tree`.
- `final_score` is computed *from* `base_score + sum(deltas)` — never stored independently, eliminating drift.

### 2.2 SpatialEngine (backend)

**File:** `backend/app/services/spatial_engine.py` (new file)

```python
class SpatialEngine:
    def query_barricade_candidates(
        self,
        corridor: str,
        event_lat: float,
        event_lon: float,
        disruption_class: str,
        requires_road_closure: bool,
        db: Session,
    ) -> list[JunctionNode]

    def get_diversion_routes(
        self,
        corridor: str,
        event_lat: float,
        event_lon: float,
        requires_road_closure: bool,
    ) -> list[DiversionRoute]
```

`query_barricade_candidates` implements the 2 km Haversine query against `junction_registry`, excludes `residential` road classes, ranks by ascending distance, and returns top-N based on `BARRICADE_COUNT_BY_CLASS`.

`get_diversion_routes` calls Valhalla (with `avoid_locations` when `requires_road_closure=True`, 5 s timeout) and falls back to the OSM cache. All returned coordinates are filtered for valid bounds before returning.

### 2.3 JunctionRegistry (database table)

**File:** `alembic/versions/<new_migration>.py`

```sql
CREATE TABLE junction_registry (
    junction_id   TEXT        PRIMARY KEY,
    corridor      TEXT        NOT NULL,
    lat           DOUBLE PRECISION NOT NULL,
    lng           DOUBLE PRECISION NOT NULL,
    road_class    TEXT        NOT NULL
        CHECK (road_class IN ('primary','secondary','tertiary','trunk','residential')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_junction_registry_corridor ON junction_registry(corridor);
```

The table is populated at startup (or via a management command) by reading from `data/processed/osm_cache.json` — no live Overpass calls at request time.

### 2.4 UnifiedStore (frontend)

**File:** `frontend/lib/store.ts` (new file — Zustand)

```typescript
interface UnifiedStoreState {
  // Slices
  livePredictions:      Record<string, Prediction>;
  activeRecommendations: Record<string, Recommendation>;
  historicalOutcomes:   Outcome[];

  // Selection
  selectedEventId: string | null;

  // Status
  loading: boolean;
  lastError: string | null;

  // Actions
  setSelectedEvent(eventId: string | null): void;
  fetchPredictionAndRecommendation(eventId: string): Promise<void>;
  submitOutcome(eventId: string, data: OutcomeInput): Promise<void>;
}
```

`setSelectedEvent(null)` clears `selectedEventId` and removes stale `livePredictions[prev]` and `activeRecommendations[prev]` entries.

`fetchPredictionAndRecommendation` fires `getPrediction` and `getRecommendation` in parallel via `Promise.allSettled` so a single failure does not block the successful slice.

### 2.5 HeatLayer (frontend)

**File:** `frontend/components/MapView.tsx` (modified)

Adds a `react-leaflet-heat` `HeatLayer` rendered inside a dedicated Leaflet pane (`heatPane`) with `zIndex: 300`. Diversion `Polyline` elements are rendered in `diversionPane` with `zIndex: 400`, guaranteeing the visual ordering invariant.

```typescript
const DISRUPTION_WEIGHT: Record<string, number> = {
  Low: 0.25, Medium: 0.5, High: 0.75, Critical: 1.0,
};

interface HeatPoint { lat: number; lng: number; weight: number; }

function toHeatPoints(predictions: Record<string, Prediction>): HeatPoint[]
```

Wrapped in a React error boundary so a Leaflet init failure degrades gracefully.

### 2.6 LearningReport Extension (backend)

**File:** `backend/app/routers/learning_report.py` (modified)

Adds `PercentageError` computation inline with the existing error loop:
- Skip outcomes where `actual_duration_min <= 0`.
- Return `null` for `mean_corrected_percentage_error` in buckets with fewer than 3 valid outcomes.
- Adds `response_model=LearningReportResponse` to enforce the contract.

### 2.7 seed_vrp_data.py (new script)

**File:** `seed_vrp_data.py` (project root)

Inserts three scenario groups using `INSERT INTO events … ON CONFLICT (event_id) DO NOTHING` and `INSERT INTO outcomes … ON CONFLICT (outcome_id) DO NOTHING`. Prints per-scenario counts to stdout. Exit code 0 in all cases.

---

## Data Models

### JunctionRegistry SQLAlchemy model

```python
class JunctionRegistry(Base):
    __tablename__ = "junction_registry"

    junction_id = Column(String, primary_key=True)
    corridor    = Column(String, nullable=False, index=True)
    lat         = Column(Float, nullable=False)
    lng         = Column(Float, nullable=False)
    road_class  = Column(String, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
```

### ReasoningTree Pydantic schema

```python
class ModifierEntrySchema(BaseModel):
    label: str
    delta: int

class ReasoningTreeSchema(BaseModel):
    disruption_class: str
    base_score:       int   # >= 0
    modifiers:        list[ModifierEntrySchema]  # max 3 entries
    final_score:      int   # >= 0
    # Runtime invariant enforced by validator:
    # base_score + sum(m.delta for m in modifiers) == final_score

    @model_validator(mode="after")
    def check_arithmetic_balance(self) -> "ReasoningTreeSchema":
        expected = self.base_score + sum(m.delta for m in self.modifiers)
        if expected != self.final_score:
            raise ValueError(f"Arithmetic imbalance: {self.base_score} + deltas = {expected} != {self.final_score}")
        return self
```

### RecommendationResponse Pydantic schema

```python
class RecommendationResponse(BaseModel):
    recommended_officers:      int
    recommended_barricades:    list[JunctionNode]
    recommended_diversions:    list[DiversionRoute]
    signals_requiring_attention: list[SignalAttention]
    baseline_comparison:       BaselineComparison
    reasoning_tree:            ReasoningTreeSchema
    barricade_reasoning_tree:  ReasoningTreeSchema
```

### LearningReportResponse Pydantic schema

```python
class BucketBreakdown(BaseModel):
    event_cause:                    str
    corridor:                       str
    n_outcomes:                     int
    mean_raw_error:                 float
    mean_corrected_error:           float
    mean_percentage_error:          Optional[float]
    mean_corrected_percentage_error: Optional[float]  # null if n < 3

class LearningReportResponse(BaseModel):
    total_outcomes_logged:           int
    mean_raw_error:                  float
    mean_corrected_error:            float
    mean_percentage_error:           Optional[float]
    mean_corrected_percentage_error: Optional[float]
    improvement_pct:                 float
    severity_raw_accuracy:           float
    per_bucket_breakdown:            list[BucketBreakdown]
```

### HeatPoint contract

```python
class HeatPoint(BaseModel):
    lat:    float   # in [-90, 90]
    lng:    float   # in [-180, 180]
    weight: float   # in [0.0, 1.0]
```

---

## API Contracts

All endpoints below receive a `response_model` annotation. FastAPI/Pydantic returns HTTP 422 on contract violations.

### GET /recommend/{event_id}

```
Response 200: RecommendationResponse
Response 404: { "detail": "Event not found" }
```

Key addition: `reasoning_tree` and `barricade_reasoning_tree` fields (see schema above).

### POST /predict

```
Request:  { "event_id": "string" }
Response 200: PredictionResponse  (extended with optional reasoning_tree: dict)
Response 404: { "detail": "Event not found" }
Response 422: Pydantic validation error
```

### GET /learning_report

```
Response 200: LearningReportResponse
```

New fields: `mean_percentage_error`, `mean_corrected_percentage_error` (top-level and per-bucket).

### HeatLayer data flow (frontend-only)

The frontend derives `HeatPoint[]` client-side from `UnifiedStore.livePredictions` — there is no dedicated heatmap API endpoint. The transformation is:

```typescript
Object.values(livePredictions)
  .filter(p => p.predicted_disruption_class != null)
  .map(p => ({
    lat:    p.latitude,
    lng:    p.longitude,
    weight: DISRUPTION_WEIGHT[p.predicted_disruption_class!],
  }))
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Arithmetic Balance Invariant

*For any* combination of `disruption_class`, `requires_road_closure`, and `event_cause`, both the officer `reasoning_tree` and the `barricade_reasoning_tree` produced by `RecommendationBuilder` SHALL satisfy `base_score + sum(m.delta for m in modifiers) == final_score`.

**Validates: Requirements 1.1, 1.3, 1.9**

### Property 2: Spatial Radius and Safety Filter

*For any* event location, corridor, and junction registry contents, every barricade candidate returned by `SpatialEngine` SHALL (a) have a Haversine distance ≤ 2.0 km from the event location, (b) have `road_class ≠ "residential"`, and (c) appear in the source `JunctionRegistry` for that corridor. When multiple candidates are returned they SHALL be ordered by ascending distance.

**Validates: Requirements 2.2, 2.4, 2.5, 2.7**

### Property 3: Coordinate Bounds Filter

*For any* set of route coordinates returned in `recommended_diversions` (regardless of whether they originate from Valhalla or the OSM cache), every `[lat, lng]` pair SHALL satisfy `lat ∈ [-90, 90]` and `lng ∈ [-180, 180]`. No out-of-bounds pair SHALL appear in the API response.

**Validates: Requirements 3.4, 9.3**

### Property 4: Percentage-Error Arithmetic Correctness

*For any* collection of outcomes where `actual_duration_min > 0`, the `PercentageError` value computed by the LearningReport endpoint SHALL equal `|predicted_duration_min − actual_duration_min| / actual_duration_min × 100`, and the corrected variant SHALL use `raw_pred = stored_prediction − active_bias` in place of `predicted_duration_min`.

**Validates: Requirements 5.1, 5.3**

### Property 5: Learning Convergence Invariant

*For any* bucket with N ≥ 3 valid outcomes (positive `actual_duration_min`), the `mean_corrected_percentage_error` returned in the per-bucket breakdown SHALL be less than or equal to `mean_percentage_error` — that is, bias correction shall not increase the average error.

**Validates: Requirements 5.6**

### Property 6: DisruptionClass Weight Mapping

*For any* `Prediction` record with a non-null `predicted_disruption_class` in `{"Low", "Medium", "High", "Critical"}`, the `HeatPoint.weight` derived by `toHeatPoints()` SHALL equal `{Low: 0.25, Medium: 0.5, High: 0.75, Critical: 1.0}[disruption_class]`, and `weight` SHALL be in the closed interval `[0.0, 1.0]`. Events with `null` or `undefined` `predicted_disruption_class` SHALL be absent from the returned `HeatPoint[]` array.

**Validates: Requirements 6.2, 6.6, 9.3**

### Property 7: Seed Script Idempotence

*For any* database state (empty or pre-populated), running `seed_vrp_data.py` a second time SHALL NOT increase the total row count of the `events` or `outcomes` tables beyond what was inserted on the first run. The script SHALL exit with code 0 on both executions.

**Validates: Requirements 7.2**

---

## Error Handling

### Backend

| Scenario | Behaviour |
|---|---|
| `disruption_class` is `None` / unknown | Default to `"Medium"`; add `fallback_class` modifier with `delta=0`; log warning |
| Valhalla timeout (>5 s) | Fall back to OSM cache; log warning with exception message |
| Valhalla non-200 response | Fall back to OSM cache; log warning with HTTP status |
| OSM cache empty after Valhalla failure | Return `recommended_diversions: []`; no exception raised |
| `requires_road_closure = None` | Treat as `False`; return empty barricade list |
| No junctions within 2 km radius | Return `recommended_barricades: []`; no exception raised |
| Unknown `disruption_class` in `BARRICADE_COUNT_BY_CLASS` | Default `N=2`; no `KeyError` |
| `actual_duration_min <= 0` in outcomes | Exclude from percentage-error computation; no `ZeroDivisionError` |
| Pydantic `ReasoningTree` arithmetic imbalance | `model_validator` raises `ValueError`; FastAPI returns HTTP 422 |

### Frontend

| Scenario | Behaviour |
|---|---|
| One of the parallel fetches fails | `Promise.allSettled` — successful slice updates; `lastError` records the failing action's message |
| `re-fetch` after outcome submission fails | `historicalOutcomes` retains the newly prepended outcome; `lastError` updated |
| HeatLayer Leaflet init throws | React error boundary catches; map renders without `HeatLayer`; no uncaught console error |
| `livePredictions` is empty | `toHeatPoints()` returns `[]`; `HeatLayer` renders with zero heat points |
| `predicted_disruption_class` is null | Event is filtered out in `toHeatPoints()` |

---

## Testing Strategy

### Unit Tests (pytest — backend)

- `test_recommendation_builder.py`: verify `ReasoningTree` field shapes, modifier inclusion rules, `None` class fallback, and empty-modifier case.
- `test_spatial_engine.py`: verify 2 km radius filter, residential exclusion, ascending-distance ordering, empty-registry handling.
- `test_learning_report.py`: verify `PercentageError` formula, zero-division guard, `null` for small buckets.
- `test_coordinate_filter.py`: verify out-of-bounds coordinates are stripped from diversion routes.

### Property-Based Tests (Hypothesis — backend)

Library: **`hypothesis`** (already available in Python ecosystem; pinned at `hypothesis==6.x`).
Each property test runs a **minimum of 100 examples** (Hypothesis default). Tag format in comments: `Feature: aegis-core-intelligence, Property N: <text>`.

**Property 1 — Arithmetic Balance Invariant**
```python
# Feature: aegis-core-intelligence, Property 1: arithmetic balance invariant
@given(
    disruption_class=st.sampled_from(["Low","Medium","High","Critical",None,"INVALID"]),
    requires_road_closure=st.booleans(),
    event_cause=st.text(min_size=1, max_size=40),
)
def test_reasoning_tree_arithmetic_balance(disruption_class, requires_road_closure, event_cause):
    builder = RecommendationBuilder()
    officer_tree = builder.build_officer_tree(disruption_class, requires_road_closure, event_cause)
    barricade_tree = builder.build_barricade_tree(disruption_class)
    assert officer_tree.base_score + sum(m.delta for m in officer_tree.modifiers) == officer_tree.final_score
    assert barricade_tree.base_score + sum(m.delta for m in barricade_tree.modifiers) == barricade_tree.final_score
```

**Property 2 — Spatial Radius and Safety Filter**
```python
# Feature: aegis-core-intelligence, Property 2: spatial radius and safety filter
@given(
    event_coords=coordinate_strategy(),
    junctions=st.lists(junction_strategy(), min_size=0, max_size=50),
    disruption_class=st.sampled_from(["Low","Medium","High","Critical"]),
)
def test_spatial_filter(event_coords, junctions, disruption_class):
    results = SpatialEngine().query_barricade_candidates_from_list(
        event_lat=event_coords[0], event_lon=event_coords[1],
        junctions=junctions, disruption_class=disruption_class, requires_road_closure=True,
    )
    for r in results:
        assert haversine_distance(event_coords[0], event_coords[1], r.lat, r.lng) <= 2.0
        assert r.road_class != "residential"
        assert r in junctions
    # Check ascending order
    dists = [haversine_distance(event_coords[0], event_coords[1], r.lat, r.lng) for r in results]
    assert dists == sorted(dists)
```

**Property 3 — Coordinate Bounds Filter**
```python
# Feature: aegis-core-intelligence, Property 3: coordinate bounds filter
@given(coords=st.lists(st.tuples(st.floats(-200,200), st.floats(-200,200)), min_size=0, max_size=100))
def test_coordinate_bounds_filter(coords):
    filtered = filter_valid_coordinates(coords)
    for lat, lng in filtered:
        assert -90 <= lat <= 90
        assert -180 <= lng <= 180
```

**Property 4 — Percentage-Error Arithmetic**
```python
# Feature: aegis-core-intelligence, Property 4: percentage-error arithmetic
@given(
    predicted=st.floats(min_value=0.1, max_value=1000.0),
    actual=st.floats(min_value=0.1, max_value=1000.0),
    bias=st.floats(min_value=-100.0, max_value=100.0),
)
def test_percentage_error_formula(predicted, actual, bias):
    pct_error = compute_percentage_error(predicted, actual)
    expected = abs(predicted - actual) / actual * 100
    assert math.isclose(pct_error, expected, rel_tol=1e-9)
    corrected_pred = predicted - bias
    corrected_pct = compute_percentage_error(corrected_pred, actual)
    corrected_expected = abs(corrected_pred - actual) / actual * 100
    assert math.isclose(corrected_pct, corrected_expected, rel_tol=1e-9)
```

**Property 5 — Learning Convergence**
```python
# Feature: aegis-core-intelligence, Property 5: learning convergence invariant
@given(outcomes=st.lists(outcome_with_bias_strategy(), min_size=3, max_size=50))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_learning_convergence(outcomes):
    mean_raw, mean_corrected = compute_bucket_errors(outcomes)
    assume(mean_raw is not None and mean_corrected is not None)
    assert mean_corrected <= mean_raw + 1e-9  # allow floating-point epsilon
```

**Property 6 — DisruptionClass Weight Mapping**
```typescript
// Feature: aegis-core-intelligence, Property 6: disruption class weight mapping
// (fc-check / fast-check in frontend tests)
fc.assert(fc.property(
  fc.record({
    predicted_disruption_class: fc.oneof(
      fc.constant("Low"), fc.constant("Medium"),
      fc.constant("High"), fc.constant("Critical"),
    ),
    latitude: fc.float({ min: -90, max: 90 }),
    longitude: fc.float({ min: -180, max: 180 }),
  }),
  (prediction) => {
    const WEIGHT = { Low: 0.25, Medium: 0.5, High: 0.75, Critical: 1.0 };
    const points = toHeatPoints({ "e1": prediction as any });
    expect(points).toHaveLength(1);
    expect(points[0].weight).toBeCloseTo(WEIGHT[prediction.predicted_disruption_class as keyof typeof WEIGHT]);
    expect(points[0].weight).toBeGreaterThanOrEqual(0.0);
    expect(points[0].weight).toBeLessThanOrEqual(1.0);
  }
), { numRuns: 100 });
```

**Property 7 — Seed Script Idempotence**
```python
# Feature: aegis-core-intelligence, Property 7: seed script idempotence
def test_seed_idempotent(tmp_db_session):
    run_seed_script(tmp_db_session)
    count_after_first = count_rows(tmp_db_session)
    run_seed_script(tmp_db_session)
    count_after_second = count_rows(tmp_db_session)
    assert count_after_first == count_after_second
```

### Integration Tests

- `test_recommend_contract.py`: POST to `/recommend/{id}` and assert response conforms to `RecommendationResponse` schema (HTTP 200, all fields present, HTTP 422 on deliberately malformed mock response).
- `test_learning_report_contract.py`: GET `/learning_report` after seed run; assert all required fields present, `mean_percentage_error` is float or null.
- `test_valhalla_fallback.py`: Mock Valhalla to timeout; assert response uses OSM cache routes and logs a warning.

### Visual Regression Gate (frontend)

A Playwright snapshot test (or Jest `@testing-library/react` assertion) verifies:

1. `heatPane` z-index (300) < `diversionPane` z-index (400) in the rendered DOM.
2. `showHeatmap={false}` prop removes the `HeatLayer` canvas element from the DOM.
3. Simulated Leaflet init error triggers the error boundary and the map still renders.

### Dual Testing Summary

| Layer | Unit | Property | Integration | Visual |
|---|---|---|---|---|
| RecommendationBuilder | ✓ | P1 | ✓ | — |
| SpatialEngine | ✓ | P2 | ✓ | — |
| Coordinate filter | ✓ | P3 | — | — |
| LearningReport | ✓ | P4, P5 | ✓ | — |
| HeatLayer / toHeatPoints | ✓ | P6 | — | ✓ |
| seed_vrp_data.py | — | P7 | ✓ | — |
| API contracts (Req 9) | — | — | ✓ | — |
