import React from "react";
import { SignalWaveform } from "./SignalWaveform";

export interface FooterWaveOverlayProps {
  userAnalyserRef: React.RefObject<AnalyserNode | null>;
  agentAnalyserRef: React.RefObject<AnalyserNode | null>;
}

export const FooterWaveOverlay: React.FC<FooterWaveOverlayProps> = ({
  userAnalyserRef,
  agentAnalyserRef,
}) => {
  return (
    <div className="relative h-14 flex-1 overflow-hidden rounded-xl bg-gradient-to-r from-indigo-50 via-slate-50 to-emerald-50 border border-slate-200/80">
      <div className="absolute inset-0 opacity-90">
        <SignalWaveform
          analyserRef={agentAnalyserRef}
          strokeColor="#818cf8"
          fillColor="rgba(129,140,248,0.15)"
          glowColor="rgba(99,102,241,0.4)"
          className="h-full"
        />
      </div>
      <div className="absolute inset-0 mix-blend-multiply opacity-80">
        <SignalWaveform
          analyserRef={userAnalyserRef}
          strokeColor="#34d399"
          fillColor="rgba(52,211,153,0.12)"
          glowColor="rgba(16,185,129,0.4)"
          className="h-full"
        />
      </div>
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.8),transparent_12%,transparent_88%,rgba(255,255,255,0.8))]" />
    </div>
  );
};
