import React from "react";
import dynamic from "next/dynamic";
import { RefreshCw } from "lucide-react";

// Dynamically import the Dashboard and explicitly disable Server-Side Rendering
const Dashboard = dynamic(() => import("../components/Dashboard"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center min-h-screen bg-slate-950 font-sans">
      <div className="flex flex-col items-center gap-4">
        <RefreshCw className="w-10 h-10 animate-spin text-accentBlue" />
        <p className="text-slate-400 font-bold animate-pulse text-xs tracking-widest uppercase">
          Loading Aegis Systems...
        </p>
      </div>
    </div>
  ),
});

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950">
      <Dashboard />
    </main>
  );
}
