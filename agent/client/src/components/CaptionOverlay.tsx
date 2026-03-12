import React, { useEffect, useState } from "react";

interface CaptionOverlayProps {
  userTranscript: string;
  agentTranscript: string;
}

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  userTranscript,
  agentTranscript,
}) => {
  const [activeText, setActiveText] = useState<{ text: string; isAgent: boolean; isVisible: boolean }>({
    text: "",
    isAgent: false,
    isVisible: false,
  });

  // When user transcript updates, promote it
  useEffect(() => {
    if (userTranscript) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveText({ text: userTranscript, isAgent: false, isVisible: true });
    }
  }, [userTranscript]);

  // When agent transcript updates, promote it
  useEffect(() => {
    if (agentTranscript) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveText({ text: agentTranscript, isAgent: true, isVisible: true });
    }
  }, [agentTranscript]);

  // Auto-hide after a period of inactivity
  useEffect(() => {
    if (!activeText.text || !activeText.isVisible) return;

    const timer = setTimeout(() => {
      setActiveText((prev) => ({ ...prev, isVisible: false }));
    }, 4000);

    return () => clearTimeout(timer);
  }, [activeText.text, activeText.isVisible]);

  if (!activeText.text) return null;

  return (
    <div
      className={`pointer-events-none absolute bottom-4 left-0 right-0 z-40 flex w-full justify-center px-4 transition-opacity duration-700 ease-in-out md:px-12 ${
        activeText.isVisible ? "opacity-100" : "opacity-0"
      }`}
    >
      <div className="max-w-4xl text-center">
        <span
          className={`box-decoration-clone rounded-lg px-3 py-1.5 text-sm font-medium leading-relaxed tracking-wide shadow-md backdrop-blur-sm ${
            activeText.isAgent
              ? "bg-indigo-50/90 text-indigo-800 border border-indigo-100"
              : "bg-slate-100/90 text-slate-600 border border-slate-200"
          }`}
        >
          {activeText.text}
        </span>
      </div>
    </div>
  );
};
