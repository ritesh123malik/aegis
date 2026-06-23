import React from "react";
import Link from "next/link";
import { ArrowLeft, Eye, RefreshCw, Layers, ShieldCheck } from "lucide-react";

export default function AboutPage() {
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
        </div>
      </main>
    </div>
  );
}
