import { ShieldAlert, Users, Compass, AlertCircle } from "lucide-react";

interface RecommendationProps {
  recommendation: {
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
    baseline_comparison?: {
      naive_baseline_officers: number;
      our_recommendation_officers: number;
      adjustment_breakdown: string;
      baseline_source: string;
    };
  } | null;
}

export default function RecommendationPanel({ recommendation }: RecommendationProps) {
  if (!recommendation) {
    return (
      <div className="h-full flex items-center justify-center text-slate-400 font-sans italic text-sm p-6 bg-slate-800 rounded-lg border border-slate-700">
        Select an event to load recommended response plan.
      </div>
    );
  }

  const {
    recommended_officers,
    recommended_barricades,
    recommended_diversions,
    signals_requiring_attention
  } = recommendation;

  return (
    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 font-sans text-slate-100 shadow-xl flex flex-col gap-4">
      <h2 className="text-sm font-black tracking-wider border-b border-slate-700 pb-2 text-slate-400 uppercase">
        TRAFFIC CONTROL RECOMMENDATIONS
      </h2>

      {/* Officers - Prominent Single Number */}
      <div className="flex flex-col bg-slate-900 border border-slate-700 p-4 rounded-lg gap-3">
        <div className="flex items-center gap-4">
          <Users className="w-10 h-10 text-blue-400" />
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
              RECOMMENDED OFFICERS
            </span>
            <div className="text-4xl font-extrabold text-white leading-none mt-1">
              {recommended_officers}
            </div>
          </div>
        </div>

        {recommendation.baseline_comparison && (
          <div className="border-t border-slate-800 pt-3 flex flex-col gap-1">
            <p className="text-[11px] text-slate-400 leading-normal">
              {recommendation.baseline_comparison.adjustment_breakdown}
            </p>
            <div className="text-xs font-semibold text-slate-350 mt-1">
              Naive baseline would suggest:{" "}
              <span className="text-slate-100 font-bold">
                {recommendation.baseline_comparison.naive_baseline_officers} officers
              </span>
            </div>
            <div className="text-[10px] text-slate-500">
              {recommendation.baseline_comparison.baseline_source}
            </div>
          </div>
        )}
      </div>

      {/* Barricades List */}
      <div className="flex flex-col gap-1.5">
        <h3 className="text-[10px] font-bold text-slate-400 tracking-wider flex items-center gap-1.5 uppercase">
          <ShieldAlert className="w-3.5 h-3.5 text-purple-400" /> BARRICADE DEPLOYMENTS ({(recommended_barricades || []).length})
        </h3>
        {recommended_barricades && recommended_barricades.length > 0 ? (
          <ul className="list-disc pl-4 text-xs text-slate-300 flex flex-col gap-1 bg-slate-900/60 p-3 rounded">
            {recommended_barricades?.map((b, idx) => (
              <li key={idx}>
                <span className="font-semibold text-slate-100">{b.junction_name}</span>{" "}
                <span className="text-[10px] text-purple-400 uppercase">({b.road_class})</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-[11px] italic text-slate-500 bg-slate-900/40 p-3 rounded border border-slate-750">
            No barricades recommended for this area.
          </div>
        )}
      </div>

      {/* Diversions List */}
      <div className="flex flex-col gap-1.5">
        <h3 className="text-[10px] font-bold text-slate-400 tracking-wider flex items-center gap-1.5 uppercase">
          <Compass className="w-3.5 h-3.5 text-purple-400" /> DIVERSION PATHS ({(recommended_diversions || []).length})
        </h3>
        {recommended_diversions && recommended_diversions.length > 0 ? (
          <ul className="list-disc pl-4 text-xs text-slate-300 flex flex-col gap-1 bg-slate-900/60 p-3 rounded">
            {recommended_diversions?.map((d, idx) => (
              <li key={idx}>
                <span className="text-slate-200">{d.description}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-[11px] italic text-slate-500 bg-slate-900/40 p-3 rounded border border-slate-750">
            No diversion routes needed.
          </div>
        )}
      </div>

      {/* Signals List */}
      <div className="flex flex-col gap-1.5">
        <h3 className="text-[10px] font-bold text-slate-400 tracking-wider flex items-center gap-1.5 uppercase">
          <AlertCircle className="w-3.5 h-3.5 text-cyan-400" /> SIGNALS REQUIRING ATTENTION
        </h3>
        {signals_requiring_attention && signals_requiring_attention.length > 0 ? (
          <ul className="list-disc pl-4 text-xs text-slate-300 flex flex-col gap-1 bg-slate-900/60 p-3 rounded">
            {signals_requiring_attention?.map((s, idx) => (
              <li key={idx}>
                <span className="font-semibold text-slate-100">Signal ID: {s.signal_id}</span>{" "}
                <span className="text-[10px] text-cyan-400 uppercase font-mono">({s.recommended_action.replace('_', ' ')})</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-[11px] italic text-slate-500 bg-slate-900/60 p-3 rounded border border-slate-750">
            No signal-controlled junctions within range
          </div>
        )}
      </div>

      {/* Bottom Honesty Disclaimer */}
      <div className="text-[10px] text-slate-500 italic mt-2 border-t border-slate-700 pt-3 text-center leading-relaxed">
        Recommendations are rules-based and grounded in real road geometry (OpenStreetMap) — not a black-box model.
      </div>
    </div>
  );
}
