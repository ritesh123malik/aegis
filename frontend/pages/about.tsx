import React, { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Eye, RefreshCw, Layers, ShieldCheck } from "lucide-react";

interface FeatureImportance {
  [key: string]: number;
}

interface ModelInfo {
  duration_model: FeatureImportance;
  severity_model: FeatureImportance;
}

export default function AboutPage() {
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${API_URL}/model_info`)
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to fetch model info");
        }
        return res.json();
      })
      .then((data: ModelInfo) => {
        setModelInfo(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "An error occurred");
        setLoading(false);
      });
  }, []);

  const getTopFeatures = (modelData: FeatureImportance | undefined) => {
    if (!modelData) return [];
    const features = Object.entries(modelData).map(([name, value]) => ({
      name,
      value: Number(value),
    }));
    // Sort descending by importance value
    features.sort((a, b) => b.value - a.value);
    return features.slice(0, 5);
  };

  const topDuration = getTopFeatures(modelInfo?.duration_model);
  const maxDuration = topDuration[0]?.value || 1;

  const topSeverity = getTopFeatures(modelInfo?.severity_model);
  const maxSeverity = topSeverity[0]?.value || 1;

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
            <Eye className="w-5 h-5 text-accentBlue" />
            <div>
              <h1 className="text-sm font-black tracking-widest text-white uppercase">AEGIS SYSTEM</h1>
              <p className="text-[9px] text-slate-400 uppercase tracking-widest font-semibold mt-0.5">
                Bengaluru Operations Command
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 max-w-4xl mx-auto w-full flex flex-col gap-8 overflow-y-auto">
        <div className="flex flex-col gap-1 border-b border-slate-800 pb-4">
          <h2 className="text-2xl font-black text-white tracking-wide uppercase">Why Aegis Is Different</h2>
          <p className="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">
            System Design &amp; Methodological Integrity
          </p>
        </div>

        <div className="flex flex-col gap-6">
          {/* Section 1 */}
          <div className="bg-slate-950 p-6 rounded-lg border border-slate-800 shadow-lg flex gap-4">
            <div className="p-3 bg-slate-900 rounded border border-slate-800 h-fit text-accentBlue">
              <RefreshCw className="w-6 h-6" />
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-lg font-bold text-white">Closed-Loop, Not Just Forecasting</h3>
              <p className="text-slate-350 text-xs leading-relaxed">
                Most traffic-impact systems stop at prediction; Aegis logs real outcomes after every event and visibly recalibrates its own predictions for that exact event type and location going forward. This closed-loop system is demonstrated live via the <strong>Outcome Form</strong>, which dynamically updates the <strong>Recalibration Viz</strong> component to correct bias and adapt system accuracy in real-time.
              </p>
            </div>
          </div>

          {/* Section 2 */}
          <div className="bg-slate-950 p-6 rounded-lg border border-slate-800 shadow-lg flex gap-4">
            <div className="p-3 bg-slate-900 rounded border border-slate-800 h-fit text-accentBlue">
              <Layers className="w-6 h-6" />
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-lg font-bold text-white">Two Honest Prediction Arms</h3>
              <p className="text-slate-350 text-xs leading-relaxed">
                Planned events (rare, ~327 real examples) and unplanned events (common, ~8,000+ examples) are fundamentally different problems. Rather than forcing a single model to predict both under-represented and over-represented event structures, Aegis utilizes two separate specialized models and highlights this distinction plainly rather than hiding it.
              </p>
            </div>
          </div>

          {/* Section 3 */}
          <div className="bg-slate-950 p-6 rounded-lg border border-slate-800 shadow-lg flex gap-4">
            <div className="p-3 bg-slate-900 rounded border border-slate-800 h-fit text-accentBlue">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-lg font-bold text-white">We Show Our Work</h3>
              <p className="text-slate-350 text-xs leading-relaxed">
                Aegis is built with transparent operations at its core. Features like the <strong>&quot;Show Calculation Audit&quot;</strong> chevron accordion in the prediction panel and the <strong>baseline comparison</strong> in the recommendation panel ensure that every recommendation and metric shown can be traced back to real computation, never an unexplained black box.
              </p>
            </div>
          </div>

          {/* Dynamic Feature Importance Panel */}
          <div className="bg-slate-950 p-6 rounded-lg border border-slate-800 shadow-lg flex flex-col gap-6">
            <div className="flex flex-col gap-1 border-b border-slate-850 pb-2">
              <h3 className="text-lg font-bold text-white uppercase tracking-wide">Model Feature Importances</h3>
              <p className="text-slate-400 text-[10px] uppercase font-semibold">Exposing production LightGBM feature weights</p>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-8 gap-2">
                <RefreshCw className="w-5 h-5 animate-spin text-accentBlue" />
                <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">Loading importances...</span>
              </div>
            ) : error ? (
              <div className="text-xs text-red-400 bg-red-950/40 border border-red-900/50 p-3 rounded">
                Failed to load model importance metadata: {error}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Duration Regression Model */}
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col">
                    <h4 className="text-sm font-extrabold text-accentBlue uppercase tracking-wider">Duration Regression Model</h4>
                    <span className="text-[9px] text-slate-500 uppercase font-semibold">Predicts minutes of planned congestion</span>
                  </div>
                  <div className="flex flex-col gap-3">
                    {topDuration.map((feat) => {
                      const pct = (feat.value / maxDuration) * 100;
                      return (
                        <div key={feat.name} className="flex flex-col gap-1">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-slate-300 font-semibold">{feat.name}</span>
                            <span className="text-slate-500">{feat.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span>
                          </div>
                          <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                            <div 
                              className="bg-accentBlue h-full rounded-full transition-all duration-500" 
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Severity Classification Model */}
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col">
                    <h4 className="text-sm font-extrabold text-accentOrange uppercase tracking-wider">Severity Classification Model</h4>
                    <span className="text-[9px] text-slate-500 uppercase font-semibold">Predicts disruption class of unplanned incidents</span>
                  </div>
                  <div className="flex flex-col gap-3">
                    {topSeverity.map((feat) => {
                      const pct = (feat.value / maxSeverity) * 100;
                      return (
                        <div key={feat.name} className="flex flex-col gap-1">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-slate-300 font-semibold">{feat.name}</span>
                            <span className="text-slate-500">{feat.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span>
                          </div>
                          <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                            <div 
                              className="bg-accentOrange h-full rounded-full transition-all duration-500" 
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
