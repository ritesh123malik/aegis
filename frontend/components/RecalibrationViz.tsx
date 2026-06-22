import { useState, useEffect } from "react";
import { getRecalibrationHistory, RecalibrationLogEntry } from "../lib/api";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { RefreshCw, LineChart as ChartIcon, HelpCircle } from "lucide-react";

interface RecalibrationVizProps {
  eventCause: string;
  corridor: string;
  latestUpdate?: RecalibrationLogEntry | null;
}

// Predefined buckets for easy demo switching
const DEMO_BUCKETS = [
  { cause: "construction", corridor: "Mysore Road", label: "Mysore Road — Construction (Mid-History)" },
  { cause: "public_event", corridor: "CBD 2", label: "CBD 2 — Public Event (No History / Flat)" },
  { cause: "vehicle_breakdown", corridor: "Bannerghata Road", label: "Bannerghatta Rd — Vehicle Breakdown" },
  { cause: "accident", corridor: "Hosur Road", label: "Hosur Road — Accident" },
  { cause: "others", corridor: "ORR East 1", label: "ORR East 1 — Waterlogging/Others" }
];

export default function RecalibrationViz({ eventCause, corridor, latestUpdate }: RecalibrationVizProps) {
  // Local bucket selection (initialized by props)
  const [selectedCause, setSelectedCause] = useState(eventCause);
  const [selectedCorridor, setSelectedCorridor] = useState(corridor);

  const [history, setHistory] = useState<RecalibrationLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sync with props whenever parent selection changes
  useEffect(() => {
    setSelectedCause(eventCause);
    setSelectedCorridor(corridor);
  }, [eventCause, corridor]);

  // Load history whenever selected bucket changes
  useEffect(() => {
    fetchHistory();
  }, [selectedCause, selectedCorridor]);

  // Append latest update locally if it belongs to the currently viewed bucket
  useEffect(() => {
    if (latestUpdate && latestUpdate.event_cause === selectedCause && latestUpdate.corridor === selectedCorridor) {
      setHistory(prev => {
        // Avoid duplicate appends if we happen to fetch and append the same thing
        const exists = prev.some(item => item.recal_id === latestUpdate.recal_id);
        if (exists) return prev;
        return [...prev, latestUpdate];
      });
    }
  }, [latestUpdate, selectedCause, selectedCorridor]);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRecalibrationHistory(selectedCause, selectedCorridor);
      setHistory(data);
    } catch (err: any) {
      setError(err.message || "Failed to load recalibration logs.");
    } finally {
      setLoading(false);
    }
  };

  const handleBucketChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const [cause, corr] = e.target.value.split("|");
    setSelectedCause(cause);
    setSelectedCorridor(corr);
  };

  // Format data for Recharts step plotting
  const chartData = history.map(item => ({
    time: new Date(item.recalibrated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    bias: parseFloat(item.new_bias_correction.toFixed(2)),
    n_outcomes: item.n_outcomes_used,
    recalibrated_at: item.recalibrated_at
  }));

  // Fallback if there is no history (flat line at zero)
  if (chartData.length === 0) {
    chartData.push({
      time: "Initial",
      bias: 0.0,
      n_outcomes: 0,
      recalibrated_at: new Date().toISOString()
    });
  }

  // Double check the latest values
  const latestEntry = history.length > 0 ? history[history.length - 1] : null;
  const nOutcomesUsed = latestEntry ? latestEntry.n_outcomes_used : 0;
  const currentBias = latestEntry ? latestEntry.new_bias_correction.toFixed(2) : "0.00";

  return (
    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 font-sans text-slate-100 shadow-xl flex flex-col gap-4">
      <div className="flex justify-between items-center border-b border-slate-700 pb-2">
        <h2 className="text-sm font-black tracking-wider text-slate-400 uppercase flex items-center gap-1.5">
          <ChartIcon className="w-4 h-4 text-accentBlue" />
          Bias Recalibration History
        </h2>
        <button
          onClick={fetchHistory}
          className="text-[9px] font-bold text-accentBlue hover:text-blue-300 flex items-center gap-1 uppercase transition-colors"
        >
          <RefreshCw className="w-2.5 h-2.5" /> Refresh
        </button>
      </div>

      {/* Bucket Selector Toggle */}
      <div className="flex flex-col gap-1">
        <label className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">
          FILTER CALIBRATION BUCKET
        </label>
        <select
          value={`${selectedCause}|${selectedCorridor}`}
          onChange={handleBucketChange}
          className="bg-slate-900 border border-slate-750 rounded p-2 text-xs text-white focus:outline-none focus:border-accentBlue"
        >
          {DEMO_BUCKETS.map((b, idx) => (
            <option key={idx} value={`${b.cause}|${b.corridor}`}>
              {b.label}
            </option>
          ))}
          {/* Dynamic option in case currently selected event isn't in predefined list */}
          {!DEMO_BUCKETS.some(b => b.cause === selectedCause && b.corridor === selectedCorridor) && (
            <option value={`${selectedCause}|${selectedCorridor}`}>
              {selectedCorridor} — {selectedCause.replace('_', ' ')} (Selected Event)
            </option>
          )}
        </select>
      </div>

      {/* Step line Chart Area */}
      <div className="w-full h-48 bg-slate-950/80 rounded border border-slate-850 p-2 relative">
        {loading && history.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-900/90 rounded">
            <RefreshCw className="w-6 h-6 animate-spin text-accentBlue" />
            <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">
              Querying calibration logs...
            </span>
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex items-center justify-center p-4 bg-slate-900/90 rounded text-red-400 text-xs text-center">
            Error: {error}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis 
                dataKey="time" 
                stroke="#64748b" 
                fontSize={8}
                tickLine={false}
              />
              <YAxis 
                stroke="#64748b" 
                fontSize={8}
                tickLine={false}
                domain={['auto', 'auto']}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: 4 }}
                labelStyle={{ fontSize: 9, fontWeight: 'bold', color: '#94a3b8' }}
                itemStyle={{ fontSize: 10, color: '#f1f5f9' }}
              />
              <Line
                type="step"
                dataKey="bias"
                name="Bias (minutes)"
                stroke="#3b82f6"
                strokeWidth={2.5}
                dot={{ r: 4, strokeWidth: 1.5, fill: '#1e293b', stroke: '#3b82f6' }}
                activeDot={{ r: 6 }}
                isAnimationActive={false} // Instant rendering for screen demo
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Proof of Learning Dashboard Stat Cards */}
      <div className="grid grid-cols-2 gap-3">
        {/* outcomes used card */}
        <div className="bg-slate-900 p-3.5 rounded border border-slate-750 flex flex-col justify-center">
          <span className="text-[9px] font-bold text-slate-500 tracking-wider uppercase">
            Outcomes Calibrated
          </span>
          <div className="text-3xl font-black text-white leading-none mt-1">
            {nOutcomesUsed}
          </div>
          <span className="text-[8px] text-slate-500 uppercase tracking-widest mt-1">
            Proof of Learning
          </span>
        </div>

        {/* current bias correction card */}
        <div className="bg-slate-900 p-3.5 rounded border border-slate-750 flex flex-col justify-center">
          <span className="text-[9px] font-bold text-slate-500 tracking-wider uppercase">
            Active Bias Shift
          </span>
          <div className="text-2xl font-black text-blue-400 leading-none mt-1.5">
            {currentBias} <span className="text-[10px] text-slate-500 font-normal">min</span>
          </div>
          <span className="text-[8px] text-slate-500 uppercase tracking-widest mt-1">
            Bias Recalibration
          </span>
        </div>
      </div>

      {/* Explanatory footer note */}
      <div className="text-[9px] text-slate-500 leading-relaxed italic border-t border-slate-700 pt-2 flex gap-1.5 items-start">
        <HelpCircle className="w-3.5 h-3.5 text-slate-500 flex-shrink-0 mt-0.5" />
        <div>
          The recalibration bias log shifts predictions dynamically when outcomes are submitted, correcting models
          by the running average of prediction error.
        </div>
      </div>
    </div>
  );
}
