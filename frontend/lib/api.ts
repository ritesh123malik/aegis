const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const mockMode = process.env.NEXT_PUBLIC_MOCK_MODE === "true";

// ==========================================
// TypeScript Interfaces matching Pydantic
// ==========================================

export interface Event {
  event_id: string;
  event_type?: string;
  event_cause?: string;
  corridor?: string;
  latitude?: number;
  longitude?: number;
  requires_road_closure?: boolean;
  priority?: string;
  start_datetime?: string;
  end_datetime?: string;
  description?: string;
  created_at?: string;
  disruption_class?: string; // fallback matching UI
}

export interface PredictionTransparency {
  raw_model_output: any;
  calibration_applied?: number | null;
  final_output: any;
  calibration_source: string;
}

export interface Prediction {
  prediction_id: number;
  event_id?: string;
  predicted_duration_min?: number;
  predicted_disruption_class?: string;
  confidence_score: number;
  recommended_officers?: number;
  recommended_barricades?: any;
  recommended_diversions?: any;
  model_version: string;
  predicted_at: string;
  low_data_warning?: boolean;
  warning_message?: string;
  prediction_transparency?: PredictionTransparency;
}

export interface Recommendation {
  recommended_officers: number;
  recommended_barricades: {
    lat: number;
    lng: number;
    junction_name: string;
    road_class: string;
  }[];
  recommended_diversions: {
    polyline: [number, number][];
    description: string;
  }[];
  signals_requiring_attention: {
    lat: number;
    lng: number;
    signal_id: string;
    recommended_action: string;
  }[];
}

export interface OutcomeInput {
  actual_duration_min: number;
  actual_disruption_class: string;
  actual_officers_deployed: number;
  notes?: string;
  logged_by: string;
}

export interface Outcome {
  outcome_id: number;
  event_id: string;
  actual_duration_min: number;
  actual_disruption_class: string;
  actual_officers_deployed: number;
  notes?: string;
  logged_by: string;
  logged_at: string;
}

export interface RecalibrationLogEntry {
  recal_id: number;
  event_cause: string;
  corridor: string;
  old_bias_correction: number;
  new_bias_correction: number;
  n_outcomes_used: number;
  recalibrated_at: string;
}

export interface OutcomeSubmissionResult {
  outcome: Outcome;
  recalibration: RecalibrationLogEntry;
}

// ==========================================
// Custom API Error Handling
// ==========================================

export class APIError extends Error {
  status: number;
  detail: any;

  constructor(status: number, message: string, detail: any) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.name = "APIError";
  }
}

async function customFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers
  });

  if (!res.ok) {
    let detail = null;
    let message = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object" && detail.msg) {
        message = detail.msg;
      } else if (Array.isArray(detail) && detail.length > 0 && detail[0].msg) {
        message = detail[0].msg;
      }
    } catch {
      // Body is not JSON
    }
    throw new APIError(res.status, message, detail);
  }

  return res.json();
}

// ==========================================
// Realistic Plausible Mock Data
// ==========================================

const MOCK_EVENTS: Event[] = [
  {
    event_id: "mock-mysore-road",
    event_type: "planned",
    event_cause: "construction",
    corridor: "Mysore Road",
    latitude: 12.9452065,
    longitude: 77.5282991,
    requires_road_closure: true,
    priority: "High",
    start_datetime: new Date().toISOString(),
    description: "Planned Metro lane extension and road widening work on Mysore Road.",
    created_at: new Date().toISOString()
  },
  {
    event_id: "mock-cbd-2",
    event_type: "planned",
    event_cause: "public_event",
    corridor: "CBD 2",
    latitude: 12.9716,
    longitude: 77.5946,
    requires_road_closure: false,
    priority: "Medium",
    start_datetime: new Date().toISOString(),
    description: "Public rally and assembly near MG Road / CBD 2 metro corridor.",
    created_at: new Date().toISOString()
  },
  {
    event_id: "mock-bannerghata",
    event_type: "unplanned",
    event_cause: "vehicle_breakdown",
    corridor: "Bannerghata Road",
    latitude: 12.9077344,
    longitude: 77.6029486,
    requires_road_closure: false,
    priority: "Low",
    start_datetime: new Date().toISOString(),
    description: "BMTC bus mechanical failure blocking one northbound lane.",
    created_at: new Date().toISOString()
  },
  {
    event_id: "mock-hosur-road",
    event_type: "unplanned",
    event_cause: "accident",
    corridor: "Hosur Road",
    latitude: 12.9429863,
    longitude: 77.6095315,
    requires_road_closure: true,
    priority: "Critical",
    start_datetime: new Date().toISOString(),
    description: "Multi-vehicle collision blocking entry to flyover ramp.",
    created_at: new Date().toISOString()
  },
  {
    event_id: "mock-orr-east",
    event_type: "unplanned",
    event_cause: "others",
    corridor: "ORR East 1",
    latitude: 12.9496901,
    longitude: 77.7008226,
    requires_road_closure: false,
    priority: "Medium",
    start_datetime: new Date().toISOString(),
    description: "Severe waterlogging near flyover due to heavy downpour.",
    created_at: new Date().toISOString()
  }
];

// ==========================================
// Typed Client Endpoint Functions
// ==========================================

export async function getEvents(filters?: { corridor?: string, event_cause?: string, limit?: number }): Promise<Event[]> {
  if (mockMode) {
    let result = [...MOCK_EVENTS];
    if (filters?.corridor) {
      result = result.filter(e => e.corridor === filters.corridor);
    }
    if (filters?.event_cause) {
      result = result.filter(e => e.event_cause === filters.event_cause);
    }
    if (filters?.limit) {
      result = result.slice(0, filters.limit);
    }
    return result;
  }

  let query = "";
  if (filters) {
    const params = new URLSearchParams();
    if (filters.corridor) params.append("corridor", filters.corridor);
    if (filters.event_cause) params.append("event_cause", filters.event_cause);
    if (filters.limit) params.append("limit", filters.limit.toString());
    query = `?${params.toString()}`;
  }

  return customFetch<Event[]>(`/events${query}`);
}

export async function getEvent(eventId: string): Promise<Event> {
  if (mockMode) {
    const matched = MOCK_EVENTS.find(e => e.event_id === eventId);
    if (!matched) throw new APIError(404, "Mock event not found", null);
    return matched;
  }

  return customFetch<Event>(`/events/${eventId}`);
}

export async function getPrediction(eventId: string): Promise<Prediction> {
  if (mockMode) {
    const event = MOCK_EVENTS.find(e => e.event_id === eventId) || MOCK_EVENTS[0];
    const isPlanned = event.event_type === "planned";
    return {
      prediction_id: Math.floor(Math.random() * 1000),
      event_id: eventId,
      predicted_duration_min: isPlanned ? 320.5 : undefined,
      predicted_disruption_class: isPlanned ? undefined : "High",
      confidence_score: isPlanned ? 0.85 : 0.38,
      model_version: "v1.0-mock",
      predicted_at: new Date().toISOString(),
      low_data_warning: !isPlanned,
      warning_message: !isPlanned 
        ? "Low historical data for this event type on this corridor — using citywide average."
        : undefined
    };
  }

  return customFetch<Prediction>(`/predict`, {
    method: "POST",
    body: JSON.stringify({ event_id: eventId })
  });
}

export async function getRecommendation(eventId: string): Promise<Recommendation> {
  if (mockMode) {
    const event = MOCK_EVENTS.find(e => e.event_id === eventId) || MOCK_EVENTS[0];
    const lat = event.latitude || 12.9716;
    const lng = event.longitude || 77.5946;
    
    return {
      recommended_officers: event.priority === "Critical" ? 17 : event.priority === "High" ? 11 : 6,
      recommended_barricades: [
        {
          lat: lat + 0.001,
          lng: lng - 0.001,
          junction_name: `${event.corridor} Sector Junction Alpha`,
          road_class: "secondary"
        },
        {
          lat: lat - 0.0012,
          lng: lng + 0.0008,
          junction_name: `${event.corridor} Sector Junction Beta`,
          road_class: "tertiary"
        }
      ],
      recommended_diversions: [
        {
          polyline: [
            [lat - 0.002, lng - 0.002],
            [lat - 0.002, lng + 0.002],
            [lat + 0.002, lng + 0.002]
          ],
          description: `${event.corridor} Bypass Route Alpha`
        }
      ],
      signals_requiring_attention: [
        {
          lat: lat + 0.0015,
          lng: lng + 0.0015,
          signal_id: "sig-mock-9921",
          recommended_action: "manual_override"
        }
      ]
    };
  }

  return customFetch<Recommendation>(`/recommend/${eventId}`);
}

export async function submitOutcome(eventId: string, outcome: OutcomeInput): Promise<OutcomeSubmissionResult> {
  if (mockMode) {
    const event = MOCK_EVENTS.find(e => e.event_id === eventId) || MOCK_EVENTS[0];
    const resultOutcome: Outcome = {
      outcome_id: Math.floor(Math.random() * 10000),
      event_id: eventId,
      actual_duration_min: outcome.actual_duration_min,
      actual_disruption_class: outcome.actual_disruption_class,
      actual_officers_deployed: outcome.actual_officers_deployed,
      notes: outcome.notes,
      logged_by: outcome.logged_by,
      logged_at: new Date().toISOString()
    };
    
    const resultRecalibration: RecalibrationLogEntry = {
      recal_id: Math.floor(Math.random() * 1000),
      event_cause: event.event_cause || "others",
      corridor: event.corridor || "Non-corridor",
      old_bias_correction: -12.5,
      new_bias_correction: -24.8,
      n_outcomes_used: 12,
      recalibrated_at: new Date().toISOString()
    };

    return {
      outcome: resultOutcome,
      recalibration: resultRecalibration
    };
  }

  const data = await customFetch<{ outcome: Outcome, recalibration_log: RecalibrationLogEntry }>(`/outcomes`, {
    method: "POST",
    body: JSON.stringify({ event_id: eventId, ...outcome })
  });

  return {
    outcome: data.outcome,
    recalibration: data.recalibration_log
  };
}

export async function getRecalibrationHistory(eventCause: string, corridor: string): Promise<RecalibrationLogEntry[]> {
  if (mockMode) {
    const now = new Date();
    return [
      {
        recal_id: 101,
        event_cause: eventCause,
        corridor: corridor,
        old_bias_correction: 0,
        new_bias_correction: -5.2,
        n_outcomes_used: 1,
        recalibrated_at: new Date(now.getTime() - 3600000 * 3).toISOString()
      },
      {
        recal_id: 102,
        event_cause: eventCause,
        corridor: corridor,
        old_bias_correction: -5.2,
        new_bias_correction: -15.8,
        n_outcomes_used: 2,
        recalibrated_at: new Date(now.getTime() - 3600000 * 2).toISOString()
      },
      {
        recal_id: 103,
        event_cause: eventCause,
        corridor: corridor,
        old_bias_correction: -15.8,
        new_bias_correction: -22.3,
        n_outcomes_used: 3,
        recalibrated_at: new Date(now.getTime() - 3600000).toISOString()
      }
    ];
  }

  return customFetch<RecalibrationLogEntry[]>(
    `/recalibration_log?event_cause=${encodeURIComponent(eventCause)}&corridor=${encodeURIComponent(corridor)}`
  );
}

export interface BucketBreakdown {
  event_cause: string;
  corridor: string;
  n_outcomes: number;
  mean_raw_error: number;
  mean_corrected_error: number;
}

export interface LearningReport {
  total_outcomes_logged: number;
  mean_raw_error: number;
  mean_corrected_error: number;
  improvement_pct: number;
  severity_raw_accuracy: number;
  per_bucket_breakdown: BucketBreakdown[];
}

export async function getLearningReport(): Promise<LearningReport> {
  if (mockMode) {
    return {
      total_outcomes_logged: 6,
      mean_raw_error: 51.67,
      mean_corrected_error: 31.67,
      improvement_pct: 38.71,
      severity_raw_accuracy: 0.67,
      per_bucket_breakdown: [
        {
          event_cause: "construction",
          corridor: "Non-corridor",
          n_outcomes: 1,
          mean_raw_error: 30.0,
          mean_corrected_error: 30.0
        },
        {
          event_cause: "others",
          corridor: "Non-corridor",
          n_outcomes: 1,
          mean_raw_error: 0.0,
          mean_corrected_error: 0.0
        },
        {
          event_cause: "public_event",
          corridor: "CBD 2",
          n_outcomes: 2,
          mean_raw_error: 62.5,
          mean_corrected_error: 32.5
        },
        {
          event_cause: "vehicle_breakdown",
          corridor: "ORR East 1",
          n_outcomes: 1,
          mean_raw_error: 0.0,
          mean_corrected_error: 0.0
        },
        {
          event_cause: "vehicle_breakdown",
          corridor: "Tumkur Road",
          n_outcomes: 1,
          mean_raw_error: 0.0,
          mean_corrected_error: 0.0
        }
      ]
    };
  }

  return customFetch<LearningReport>("/learning_report");
}

export interface SimilarEvent {
  event_id: string;
  event_type: string;
  event_cause: string;
  corridor: string;
  start_datetime: string | null;
  requires_road_closure: boolean;
  similarity_score: number;
  outcome: {
    actual_duration_min: number | null;
    actual_disruption_class: string | null;
    notes: string | null;
  } | null;
}

export async function getSimilarEvents(eventId: string): Promise<SimilarEvent[]> {
  if (mockMode) {
    return [
      {
        event_id: "mock-similar-1",
        event_type: "planned",
        event_cause: "construction",
        corridor: "Mysore Road",
        start_datetime: new Date().toISOString(),
        requires_road_closure: true,
        similarity_score: 0.95,
        outcome: {
          actual_duration_min: 120.0,
          actual_disruption_class: "Critical",
          notes: "Metro lane widening finished with slight delay"
        }
      },
      {
        event_id: "mock-similar-2",
        event_type: "planned",
        event_cause: "construction",
        corridor: "Mysore Road",
        start_datetime: new Date().toISOString(),
        requires_road_closure: true,
        similarity_score: 0.88,
        outcome: null
      }
    ];
  }

  return customFetch<SimilarEvent[]>(`/similar_events/${eventId}`);
}
