import { AlertTriangle } from "lucide-react";

interface PredictionProps {
  prediction: {
    predicted_duration_min?: number;
    predicted_disruption_class?: string;
    confidence_score: number;
    low_data_warning?: boolean;
    warning_message?: string;
  } | null;
  eventType?: string;
}

const LOW_CONFIDENCE_THRESHOLD = 0.5;

export default function PredictionPanel({ prediction, eventType }: PredictionProps) {
  if (!prediction) {
    return (
      <div className="h-full flex items-center justify-center text-slate-400 font-sans italic text-sm p-6 bg-slate-800 rounded-lg border border-slate-700">
        Select an event to run live prediction engine.
      </div>
    );
  }

  const confidence = prediction.confidence_score;
  const isLowConfidence = confidence < LOW_CONFIDENCE_THRESHOLD;

  // Derive uncertainty range proportional to (1 - confidence)
  const uncertainty = 1 - confidence;
  const rangeMin = Math.max(0, confidence - uncertainty / 2);
  const rangeMax = Math.min(1, confidence + uncertainty / 2);

  return (
    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 font-sans text-slate-100 shadow-xl flex flex-col gap-4">
      <h2 className="text-sm font-black tracking-wider border-b border-slate-700 pb-2 text-slate-400 uppercase">
        LIVE INFERENCE ENGINE
      </h2>

      <div className="flex flex-col gap-1">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {eventType === "planned" ? "PREDICTED DURATION" : "PREDICTED DISRUPTION CLASS"}
        </span>
        <div className="text-3xl font-black tracking-tight text-white">
          {eventType === "planned" ? (
            prediction.predicted_duration_min !== undefined ? (
              <span>
                {Math.round(prediction.predicted_duration_min)}{" "}
                <span className="text-sm font-semibold text-slate-400">minutes</span>
              </span>
            ) : (
              "N/A"
            )
          ) : (
            <span className="capitalize">{prediction.predicted_disruption_class || "N/A"}</span>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center text-[10px] font-bold tracking-wider text-slate-500">
          <span>MODEL CONFIDENCE &amp; UNCERTAINTY RANGE</span>
          <span className={isLowConfidence ? "text-amber-500" : "text-emerald-500"}>
            {Math.round(confidence * 100)}%
          </span>
        </div>

        {/* Shaded uncertainty range container */}
        <div className="w-full h-4 bg-slate-950 rounded relative overflow-hidden border border-slate-800">
          {/* Uncertainty Range Shading */}
          <div 
            className="absolute h-full bg-slate-700/60 opacity-50"
            style={{ 
              left: `${rangeMin * 100}%`, 
              width: `${(rangeMax - rangeMin) * 100}%` 
            }}
          />
          {/* Primary confidence bar */}
          <div
            className={`h-full transition-all duration-500 absolute left-0 top-0 ${
              isLowConfidence 
                ? "bg-amber-600/40 border border-dashed border-amber-500" 
                : "bg-emerald-500"
            }`}
            style={{ width: `${confidence * 100}%` }}
          />
        </div>
        
        <div className="flex justify-between text-[8px] text-slate-500 font-mono">
          <span>0.0 (LOW)</span>
          <span>0.5</span>
          <span>1.0 (HIGH)</span>
        </div>
      </div>

      {prediction.low_data_warning && (
        <div className="flex gap-3 bg-red-950/80 border-2 border-red-600 p-4 rounded text-red-200 shadow-md">
          <AlertTriangle className="w-6 h-6 flex-shrink-0 text-red-500" />
          <div className="text-[11px] leading-relaxed">
            <span className="font-extrabold text-red-400 block mb-0.5 text-xs uppercase tracking-wide">
              HONESTY BANNER
            </span>
            Low historical data for this event type on this corridor — using citywide average.
          </div>
        </div>
      )}
    </div>
  );
}
