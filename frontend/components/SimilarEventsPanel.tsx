import { SimilarEvent } from "../lib/api";
import { History, CheckCircle, AlertTriangle, AlertCircle, Clock, Calendar } from "lucide-react";

interface SimilarEventsProps {
  similarEvents: SimilarEvent[] | null;
  loading: boolean;
}

export default function SimilarEventsPanel({ similarEvents, loading }: SimilarEventsProps) {
  if (loading) {
    return (
      <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 font-sans text-slate-400 flex flex-col items-center justify-center gap-3">
        <Clock className="w-6 h-6 animate-spin text-accentBlue" />
        <span className="text-[10px] uppercase font-bold tracking-wider">Loading similar incidents...</span>
      </div>
    );
  }

  if (!similarEvents || similarEvents.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-slate-400 font-sans italic text-sm p-6 bg-slate-800 rounded-lg border border-slate-700">
        Select an event to view similar past occurrences.
      </div>
    );
  }

  return (
    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 font-sans text-slate-100 shadow-xl flex flex-col gap-4">
      <div className="flex items-center gap-2 border-b border-slate-700 pb-2">
        <History className="w-4 h-4 text-accentBlue" />
        <h2 className="text-sm font-black tracking-wider text-slate-400 uppercase">
          SIMILAR PAST EVENTS ({similarEvents.length})
        </h2>
      </div>

      <div className="flex flex-col gap-3.5">
        {similarEvents.map((ev, idx) => {
          const matchPercent = (ev.similarity_score * 100).toFixed(1);
          const causeText = ev.event_cause ? ev.event_cause.replace(/_/g, " ") : "Unknown";
          const formattedDate = ev.start_datetime 
            ? new Date(ev.start_datetime).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit"
              }) 
            : "Unknown Date";

          return (
            <div key={ev.event_id || idx} className="bg-slate-900 border border-slate-750 p-3.5 rounded flex flex-col gap-2.5">
              
              {/* Corridor & Similarity Match */}
              <div className="flex justify-between items-start">
                <span className="font-bold text-slate-200 text-xs truncate max-w-[70%]">
                  {ev.corridor || "Bengaluru Road"}
                </span>
                <span className="px-2 py-0.5 rounded-[2px] text-[9px] font-black tracking-wide uppercase bg-blue-950 text-blue-300 border border-blue-900">
                  {matchPercent}% Match
                </span>
              </div>

              {/* Event Metadata Grid */}
              <div className="grid grid-cols-2 gap-x-2 gap-y-1.5 text-[10px] text-slate-400">
                <div className="flex justify-between">
                  <span className="text-slate-500">Cause:</span>
                  <span className="capitalize text-slate-300 font-semibold">{causeText}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Type:</span>
                  <span className="capitalize text-slate-300">{ev.event_type}</span>
                </div>
                <div className="flex justify-between col-span-2">
                  <span className="text-slate-500">Start Time:</span>
                  <span className="text-slate-350 flex items-center gap-1" suppressHydrationWarning>
                    <Calendar className="w-3 h-3 text-slate-500" /> {formattedDate}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Road Closure:</span>
                  <span className="text-slate-300">{ev.requires_road_closure ? "Yes" : "No"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">ID:</span>
                  <span className="font-mono text-slate-350 select-all">{ev.event_id.slice(0, 8)}</span>
                </div>
              </div>

              {/* Real Outcome Section */}
              <div className="border-t border-slate-800 pt-2 flex flex-col gap-1.5">
                {ev.outcome ? (
                  <div className="bg-emerald-950/20 border border-emerald-900/60 p-2.5 rounded text-[10px] leading-relaxed flex flex-col gap-1 text-emerald-300">
                    <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-[9px] text-emerald-400">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> REAL OUTCOME ON RECORD
                    </div>
                    {ev.outcome.actual_duration_min !== null && (
                      <div>
                        <span className="text-slate-400 font-normal">Actual Duration: </span>
                        <span className="font-semibold text-emerald-200">{ev.outcome.actual_duration_min} min</span>
                      </div>
                    )}
                    {ev.outcome.actual_disruption_class && (
                      <div>
                        <span className="text-slate-400 font-normal">Actual Severity: </span>
                        <span className="font-semibold text-emerald-200">{ev.outcome.actual_disruption_class}</span>
                      </div>
                    )}
                    {ev.outcome.notes && (
                      <div className="text-[10px] text-slate-300 bg-slate-950/40 p-1.5 rounded mt-0.5 border border-slate-900 italic">
                        "{ev.outcome.notes}"
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="bg-slate-950/40 border border-slate-850 p-2 rounded text-[10px] text-slate-500 flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-slate-600" />
                    <span className="uppercase font-bold tracking-wider text-[8px] text-slate-600">
                      No real outcome on record
                    </span>
                  </div>
                )}
              </div>

            </div>
          );
        })}
      </div>

      <div className="text-[10px] text-slate-500 italic mt-2 border-t border-slate-700 pt-3 text-center leading-relaxed">
        Similarity scores are calculated deterministically using cause matching, spatial centroids proximity, and circular time-of-day similarity.
      </div>
    </div>
  );
}
