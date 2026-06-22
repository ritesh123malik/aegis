import { useState, useEffect } from "react";
import Link from "next/link";
import { getLearningReport, LearningReport } from "../lib/api";
import { ArrowLeft, BookOpen, RefreshCw, AlertTriangle, TrendingUp, ShieldAlert, Award, Activity } from "lucide-react";

export default function LearningReportPage() {
  const [report, setReport] = useState<LearningReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLearningReport();
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Failed to fetch learning report from backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, []);

  return (
    <div className="min-h-screen w-screen bg-slate-900 text-slate-100 font-sans flex flex-col overflow-x-hidden">
      
      {/* Header */}
      <header className="p-4 border-b border-slate-700 bg-slate-950 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-1.5 text-xs font-bold text-accentBlue hover:text-blue-300 transition-colors uppercase">
            <ArrowLeft className="w-4 h-4" /> Mission Control
          </Link>
          <div className="h-4 w-[1px] bg-slate-700" />
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-accentBlue" />
            <div>
              <h1 className="text-sm font-black tracking-widest text-white uppercase">AEGIS SYSTEM</h1>
              <p className="text-[9px] text-slate-400 uppercase tracking-widest font-semibold mt-0.5">
                Aggregate Bias Recalibration &amp; Learning Report
              </p>
            </div>
          </div>
        </div>

        <button 
          onClick={fetchReport}
          className="text-xs font-bold text-accentBlue hover:text-blue-300 flex items-center gap-1.5 uppercase transition-colors px-3 py-1.5 border border-slate-800 rounded bg-slate-900"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Report
        </button>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full flex flex-col gap-6 overflow-y-auto">
        
        <div className="flex flex-col gap-1">
          <h2 className="text-xl font-extrabold text-white tracking-wide">Recalibration Engine Performance</h2>
          <p className="text-slate-400 text-xs">
            This dashboard aggregates active operations feedback system-wide, validating how post-event outcomes adjust prediction errors over time.
          </p>
        </div>

        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center py-20 gap-3">
            <RefreshCw className="w-10 h-10 animate-spin text-accentBlue" />
            <span className="text-xs text-slate-500 tracking-wider font-bold uppercase">
              Analyzing historical feedback loops...
            </span>
          </div>
        ) : error ? (
          <div className="flex gap-3 bg-red-950 border border-red-800 p-5 rounded text-red-200 shadow-xl max-w-xl mx-auto mt-10">
            <ShieldAlert className="w-6 h-6 flex-shrink-0 text-red-500" />
            <div className="text-xs leading-relaxed">
              <span className="font-black block mb-1 uppercase text-red-400">
                Learning Report Analysis Failed
              </span>
              {error}
            </div>
          </div>
        ) : !report ? (
          <div className="text-center py-20 text-slate-400 italic text-sm">
            No analysis results available.
          </div>
        ) : (
          <>
            {/* Warning note for small sample size */}
            {report.total_outcomes_logged < 10 && (
              <div className="flex gap-2.5 bg-amber-950/40 border border-amber-900 p-3.5 rounded text-amber-200 text-xs shadow-md">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-500 mt-0.5" />
                <div>
                  <span className="font-extrabold uppercase text-amber-400 block mb-0.5">Note on Data Volatility</span>
                  Limited real outcome history so far — this report strengthens as more events are logged.
                </div>
              </div>
            )}

            {/* Stat Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              
              {/* Outcomes Logged */}
              <div className="bg-slate-950 border border-slate-800 p-5 rounded shadow-lg flex flex-col gap-2 relative overflow-hidden">
                <div className="absolute right-3 top-3 text-slate-800">
                  <Activity className="w-12 h-12 stroke-[1.5]" />
                </div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Total Outcomes
                </span>
                <span className="text-3xl font-black text-white leading-none">
                  {report.total_outcomes_logged}
                </span>
                <span className="text-[10px] text-slate-500 mt-1">
                  Cumulative logged outcomes in system
                </span>
              </div>

              {/* Mean Raw Error */}
              <div className="bg-slate-950 border border-slate-800 p-5 rounded shadow-lg flex flex-col gap-2 relative overflow-hidden">
                <div className="absolute right-3 top-3 text-slate-800">
                  <ShieldAlert className="w-12 h-12 stroke-[1.5]" />
                </div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Mean Raw Error
                </span>
                <span className="text-3xl font-black text-slate-300 leading-none">
                  {report.mean_raw_error.toFixed(2)}<span className="text-sm font-semibold ml-0.5">m</span>
                </span>
                <span className="text-[10px] text-slate-500 mt-1">
                  Baseline duration error (uncorrected)
                </span>
              </div>

              {/* Mean Corrected Error */}
              <div className="bg-slate-950 border border-slate-800 p-5 rounded shadow-lg flex flex-col gap-2 relative overflow-hidden">
                <div className="absolute right-3 top-3 text-slate-800">
                  <Award className="w-12 h-12 stroke-[1.5]" />
                </div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Mean Corrected Error
                </span>
                <span className="text-3xl font-black text-white leading-none">
                  {report.mean_corrected_error.toFixed(2)}<span className="text-sm font-semibold ml-0.5">m</span>
                </span>
                <span className="text-[10px] text-slate-500 mt-1">
                  Post-recalibration duration error
                </span>
              </div>

              {/* Improvement Pct */}
              <div className="bg-slate-950 border border-slate-800 p-5 rounded shadow-lg flex flex-col gap-2 relative overflow-hidden">
                <div className="absolute right-3 top-3 text-slate-800">
                  <TrendingUp className="w-12 h-12 stroke-[1.5]" />
                </div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Improvement Rate
                </span>
                <span className={`text-3xl font-black leading-none ${report.improvement_pct > 0 ? 'text-emerald-400' : report.improvement_pct < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                  {report.improvement_pct > 0 ? '+' : ''}{report.improvement_pct.toFixed(1)}%
                </span>
                <span className="text-[10px] text-slate-500 mt-1">
                  Average error reduction by bias correction
                </span>
              </div>

            </div>

            {/* Additional Sub-metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-slate-950 border border-slate-800 p-4 rounded text-xs flex justify-between items-center">
                <div>
                  <span className="font-extrabold uppercase text-slate-300 block">Severity Classification Accuracy</span>
                  <span className="text-slate-500 mt-0.5 block">Overall recall rate for unplanned incident severity predictions</span>
                </div>
                <span className="text-2xl font-black text-accentBlue px-4 py-2 bg-slate-900 rounded border border-slate-800">
                  {(report.severity_raw_accuracy * 100).toFixed(0)}%
                </span>
              </div>
              <div className="bg-slate-950 border border-slate-800 p-4 rounded text-xs flex items-center justify-between">
                <div>
                  <span className="font-extrabold uppercase text-slate-300 block">Calibration Health</span>
                  <span className="text-slate-500 mt-0.5 block">Status of active feedback loop across corridors</span>
                </div>
                <span className={`px-2.5 py-1 rounded-[2px] text-[10px] tracking-wide font-black uppercase border ${
                  report.total_outcomes_logged > 0 
                    ? "bg-emerald-950 text-emerald-300 border-emerald-900" 
                    : "bg-slate-900 text-slate-400 border-slate-850"
                }`}>
                  {report.total_outcomes_logged > 0 ? "Active Calibration" : "Idle (Awaiting Data)"}
                </span>
              </div>
            </div>

            {/* Detailed Bucket Table */}
            <div className="bg-slate-950 border border-slate-800 rounded shadow-lg overflow-hidden flex flex-col">
              <div className="p-4 border-b border-slate-850 bg-slate-900 flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                  Operational Bucket Breakdown (Causes / Corridors)
                </span>
                <span className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">
                  Showing {report.per_bucket_breakdown.length} unique buckets
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-900 border-b border-slate-800 text-slate-400 font-bold uppercase text-[9px] tracking-wider">
                      <th className="py-3 px-4">Event Cause</th>
                      <th className="py-3 px-4">Corridor</th>
                      <th className="py-3 px-4 text-center">Outcomes logged ($n$)</th>
                      <th className="py-3 px-4 text-right">Mean Raw Error</th>
                      <th className="py-3 px-4 text-right">Mean Corrected Error</th>
                      <th className="py-3 px-4 text-right">Improvement (min)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-850">
                    {report.per_bucket_breakdown.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-500 italic">
                          No outcomes logged for any bucket.
                        </td>
                      </tr>
                    ) : (
                      report.per_bucket_breakdown.map((b, idx) => {
                        const diff = b.mean_raw_error - b.mean_corrected_error;
                        const causeText = b.event_cause.replace(/_/g, " ");
                        return (
                          <tr key={idx} className="hover:bg-slate-900/50 transition-colors">
                            <td className="py-3 px-4 font-bold capitalize text-slate-200">{causeText}</td>
                            <td className="py-3 px-4 text-slate-350">{b.corridor}</td>
                            <td className="py-3 px-4 text-center font-mono text-slate-200">{b.n_outcomes}</td>
                            <td className="py-3 px-4 text-right font-mono text-slate-400">{b.mean_raw_error.toFixed(1)}m</td>
                            <td className="py-3 px-4 text-right font-mono text-slate-200">{b.mean_corrected_error.toFixed(1)}m</td>
                            <td className={`py-3 px-4 text-right font-mono font-bold ${diff > 0.05 ? 'text-emerald-400' : diff < -0.05 ? 'text-rose-400' : 'text-slate-400'}`}>
                              {diff > 0.05 ? '+' : ''}{diff.toFixed(1)}m
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </main>

      {/* Footer Branding */}
      <footer className="p-4 border-t border-slate-800 bg-slate-950 text-center text-[10px] text-slate-500 tracking-wider uppercase flex-shrink-0 mt-auto">
        Aegis Analytics Engine &bull; Confidential Operations Dashboard
      </footer>

    </div>
  );
}
