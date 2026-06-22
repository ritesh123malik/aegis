import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { getEvents, getPrediction, getRecommendation, Event, Prediction, Recommendation, RecalibrationLogEntry, OutcomeSubmissionResult } from "../lib/api";
import PredictionPanel from "../components/PredictionPanel";
import RecommendationPanel from "../components/RecommendationPanel";
import OutcomeForm from "../components/OutcomeForm";
import RecalibrationViz from "../components/RecalibrationViz";
import { AlertOctagon, RefreshCw, Eye, MapPin } from "lucide-react";

const MapView = dynamic(() => import("../components/MapView"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900 text-slate-400 gap-4">
      <RefreshCw className="w-10 h-10 animate-spin text-accentBlue" />
      <span className="font-sans text-xs tracking-widest font-extrabold uppercase">
        Initializing Mission Control Interface...
      </span>
    </div>
  ),
});

export default function Dashboard() {
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [latestOutcomeUpdate, setLatestOutcomeUpdate] = useState<RecalibrationLogEntry | null>(null);

  const [loadingEvents, setLoadingEvents] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [errorEvents, setErrorEvents] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<string | null>(null);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    setLoadingEvents(true);
    setErrorEvents(null);
    try {
      const data = await getEvents();
      setEvents(data);
      if (data.length > 0) {
        // Automatically select the first event
        handleEventSelect(data[0].event_id);
      }
    } catch (err: any) {
      setErrorEvents(err.message || "Failed to load events from http://localhost:8000/events");
    } finally {
      setLoadingEvents(false);
    }
  };

  const handleEventSelect = async (eventId: string) => {
    setSelectedEventId(eventId);
    setLoadingDetails(true);
    setErrorDetails(null);
    setPrediction(null);
    setRecommendation(null);
    setLatestOutcomeUpdate(null); // Clear previous updates
    try {
      const [pred, rec] = await Promise.all([
        getPrediction(eventId),
        getRecommendation(eventId)
      ]);
      setPrediction(pred);
      setRecommendation(rec);
    } catch (err: any) {
      setErrorDetails(err.message || "Failed to fetch prediction/recommendation from backend.");
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleOutcomeSubmitted = (result: OutcomeSubmissionResult) => {
    // 1. Pass the recalibration log to update the chart in real-time
    setLatestOutcomeUpdate(result.recalibration_log);
    
    // 2. Refetch prediction/recommendation details so that the bias-corrected prediction shifts instantly on screen!
    if (selectedEventId) {
      // Re-run details fetching silently (no loading spinner) so prediction updates smoothly
      Promise.all([
        getPrediction(selectedEventId),
        getRecommendation(selectedEventId)
      ]).then(([pred, rec]) => {
        setPrediction(pred);
        setRecommendation(rec);
      }).catch(err => {
        console.error("Failed to silently refetch prediction after outcome:", err);
      });
    }
  };

  const selectedEvent = events.find(e => e.event_id === selectedEventId);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-900 text-slate-100 font-sans">
      
      {/* Left Sidebar: Logo and Active Incidents List */}
      <div className="w-[25%] h-full border-r border-slate-700 bg-slate-950 flex flex-col flex-shrink-0">
        
        {/* Header Branding */}
        <div className="p-4 border-b border-slate-700 bg-slate-900 flex items-center gap-2">
          <Eye className="w-6 h-6 text-accentBlue animate-pulse" />
          <div>
            <h1 className="text-sm font-black tracking-widest text-white uppercase">AEGIS SYSTEM</h1>
            <p className="text-[9px] text-slate-400 uppercase tracking-widest font-semibold mt-0.5">
              Bengaluru Operations Command
            </p>
          </div>
        </div>

        {/* Incidents List Container */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
          {loadingEvents ? (
            <div className="flex flex-col items-center justify-center p-8 gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-accentBlue" />
              <span className="text-[10px] text-slate-500 tracking-wider font-bold uppercase">
                Retrieving active incidents...
              </span>
            </div>
          ) : errorEvents ? (
            <div className="flex gap-2 bg-red-950 border border-red-800 p-4 rounded text-red-200 shadow-lg">
              <AlertOctagon className="w-5 h-5 flex-shrink-0 text-red-500" />
              <div className="text-[11px] leading-relaxed">
                <span className="font-extrabold block mb-0.5 uppercase text-red-400">
                  Event Fetch Failed
                </span>
                {errorEvents}
              </div>
            </div>
          ) : events.length === 0 ? (
            <div className="text-center p-8 bg-slate-900 border border-slate-850 rounded text-slate-400 italic text-xs">
              No active incidents in system database.
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  ACTIVE INCIDENTS ({events.length})
                </span>
                <button 
                  onClick={fetchEvents}
                  className="text-[9px] font-bold text-accentBlue hover:text-blue-300 flex items-center gap-1 uppercase transition-colors"
                >
                  <RefreshCw className="w-2.5 h-2.5" /> Refresh
                </button>
              </div>
              <div className="flex flex-col gap-2">
                {events.map(ev => {
                  const isSelected = ev.event_id === selectedEventId;
                  const causeText = ev.event_cause ? ev.event_cause.replace(/_/g, " ") : "Unknown";
                  return (
                    <button
                      key={ev.event_id}
                      onClick={() => handleEventSelect(ev.event_id)}
                      className={`text-left p-3 rounded border text-[11px] transition-all duration-150 ${
                        isSelected 
                          ? "bg-slate-800 border-accentBlue text-white shadow-md shadow-blue-500/10" 
                          : "bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-850 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex justify-between items-start font-bold">
                        <span className="text-slate-100 truncate w-[70%] text-[12px]">
                          {ev.corridor || "Bengaluru Road"}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded-[2px] text-[8px] tracking-wide font-black uppercase border ${
                          ev.event_type === "planned" 
                            ? "bg-blue-950 text-blue-300 border-blue-900" 
                            : "bg-amber-950 text-amber-300 border-amber-900"
                        }`}>
                          {ev.event_type}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 capitalize mt-1">
                        Cause: {causeText}
                      </div>
                      {ev.description && (
                        <div className="text-slate-500 mt-1 text-[9px] truncate">
                          {ev.description}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Dossier details card */}
          {selectedEvent && (
            <div className="bg-slate-900 p-4 rounded border border-slate-850 flex flex-col gap-2.5 mt-auto">
              <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase border-b border-slate-800 pb-1.5 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-accentBlue" /> Incident Dossier
              </span>
              <div className="flex flex-col gap-1.5 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-slate-500">ID:</span> 
                  <span className="font-mono text-slate-300 select-all">{selectedEvent.event_id.slice(0, 8)}...</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Cause:</span> 
                  <span className="capitalize text-slate-350">{selectedEvent.event_cause.replace(/_/g, ' ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Priority:</span> 
                  <span className="text-slate-350">{selectedEvent.priority || "Normal"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Closure:</span> 
                  <span className="text-slate-350">{selectedEvent.requires_road_closure ? "YES" : "NO"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Coordinates:</span> 
                  <span className="font-mono text-slate-350">{selectedEvent.latitude.toFixed(5)}, {selectedEvent.longitude.toFixed(5)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Middle Pane: Map View */}
      <div className="flex-1 h-full relative">
        <MapView
          events={events}
          selectedEventId={selectedEventId}
          onEventSelect={handleEventSelect}
          barricades={recommendation?.recommended_barricades}
          diversions={recommendation?.recommended_diversions}
          signals={recommendation?.signals_requiring_attention}
        />
      </div>

      {/* Right Sidebar: Prediction, Recommendation, Outcome Form, Recalibration History */}
      <div className="w-[30%] h-full border-l border-slate-700 bg-slate-950 flex flex-col flex-shrink-0 overflow-y-auto p-4 gap-4">
        {loadingDetails ? (
          <div className="h-full flex flex-col items-center justify-center p-8 gap-3">
            <RefreshCw className="w-8 h-8 animate-spin text-accentBlue" />
            <span className="text-[10px] text-slate-500 tracking-wider uppercase font-bold text-center">
              Generating Response &amp; Inference Plans...
            </span>
          </div>
        ) : errorDetails ? (
          <div className="flex gap-2 bg-red-950 border border-red-800 p-4 rounded text-red-200 shadow-lg">
            <AlertOctagon className="w-5 h-5 flex-shrink-0 text-red-500" />
            <div className="text-[11px] leading-relaxed">
              <span className="font-extrabold block mb-0.5 uppercase text-red-400">
                Inference System Error
              </span>
              {errorDetails}
            </div>
          </div>
        ) : (
          <>
            <PredictionPanel 
              prediction={prediction} 
              eventType={selectedEvent?.event_type}
            />
            <RecommendationPanel 
              recommendation={recommendation}
            />
            {selectedEvent && (
              <>
                <OutcomeForm
                  eventId={selectedEvent.event_id}
                  onSubmitted={handleOutcomeSubmitted}
                />
                <RecalibrationViz
                  eventCause={selectedEvent.event_cause}
                  corridor={selectedEvent.corridor}
                  latestUpdate={latestOutcomeUpdate}
                />
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
