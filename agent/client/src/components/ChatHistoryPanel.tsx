import React, { useEffect, useRef } from "react";
import { marked } from "marked";
import { X, BookOpen } from "lucide-react";
import type { ChatMessage } from "@/hooks/useLiveSocket";

interface ChatHistoryPanelProps {
  messages: ChatMessage[];
  isOpen: boolean;
  onClose: () => void;
  isDesktop: boolean;
}

// Configure marked for safe output
marked.setOptions({
  breaks: true,
  gfm: true,
});

export const ChatHistoryPanel: React.FC<ChatHistoryPanelProps> = ({
  messages,
  isOpen,
  onClose,
  isDesktop,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change or panel opens
  useEffect(() => {
    if (scrollRef.current) {
      // Use requestAnimationFrame to ensure DOM has updated before scrolling
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });
    }
  }, [messages, isOpen]);

  if (!isOpen && !isDesktop) return null;

  const panelClasses = isDesktop
    ? "relative w-[320px] lg:w-[380px] flex-shrink-0 border-l border-slate-200 z-10 h-full hidden md:flex"
    : "fixed inset-0 z-[90] shadow-2xl";

  return (
    <div className={`${panelClasses} flex flex-col bg-white fade-in`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-indigo-600" />
          <span className="text-sm font-bold text-slate-800">Conversation</span>
          <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-600">
            {messages.length}
          </span>
        </div>
        {!isDesktop && (
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 space-y-3"
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 opacity-60">
            <BookOpen className="h-10 w-10 text-slate-300" />
            <p className="text-sm text-slate-400">
              Conversation history will appear here
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="fade-in">
              {msg.type === "guide" || msg.isGuide ? (
                <CopyTextCard
                  timestamp={msg.timestamp}
                  toolData={msg.toolData}
                />
              ) : (
                <TranscriptBubble
                  text={msg.text}
                  isAgent={msg.isAgent}
                  timestamp={msg.timestamp}
                  type={msg.type}
                  isPartial={msg.isPartial}
                  toolData={msg.toolData}
                />
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

/** Regular transcript bubble */
const TranscriptBubble: React.FC<{
  text: string;
  isAgent: boolean;
  timestamp: number;
  type?: ChatMessage["type"];
  isPartial?: boolean;
  toolData?: any;
}> = ({ text, isAgent, timestamp, type, isPartial, toolData }) => {
  const time = new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  if (type === "tool_response") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs text-slate-500 rounded-tl-md">
          <div className="flex items-center gap-1 font-semibold text-slate-600 mb-1">
            <span className="h-2 w-2 rounded-full bg-slate-300" />
            Tool Called
          </div>
          <p className="font-mono text-[10px] break-all">
            {toolData && typeof toolData === "object"
              ? JSON.stringify(toolData, null, 2)
              : String(toolData)}
          </p>
          <p className="mt-1 text-[10px] text-slate-400">{time}</p>
        </div>
      </div>
    );
  }

  const isTranscription =
    type === "input_transcription" || type === "output_transcription";

  return (
    <div className={`flex ${isAgent ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isAgent
            ? "bg-slate-100 text-slate-700 rounded-tl-md"
            : "bg-indigo-600 text-white rounded-tr-md"
        } ${isTranscription ? "opacity-90 italic" : ""}`}
      >
        <p>
          {text}
          {isPartial && (
            <span className="animate-pulse ml-0.5 opacity-60">...</span>
          )}
        </p>
        <p
          className={`mt-1 text-[10px] flex items-center gap-1 ${
            isAgent ? "text-slate-400" : "text-indigo-200"
          }`}
        >
          {time}
          {isTranscription && <span className="opacity-70">(Spoken)</span>}
        </p>
      </div>
    </div>
  );
};

/** Snippet card for copying text */
const CopyTextCard: React.FC<{
  timestamp: number;
  toolData?: any;
}> = ({ timestamp, toolData }) => {
  const time = new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  const items = (toolData?.items as Array<{label: string, text: string}>) || [];
  const explanation = toolData?.explanation || "Here is the information you need:";

  const handleCopy = (textToCopy: string) => {
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy).catch((err) => {
        console.error("Failed to copy text: ", err);
      });
    }
  };

  return (
    <div className="rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <BookOpen className="h-3.5 w-3.5 text-indigo-500" />
        <span className="text-[11px] font-semibold text-indigo-600 uppercase tracking-wider">
          {explanation}
        </span>
        <span className="ml-auto text-[10px] text-slate-400">{time}</span>
      </div>
      
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={index} className="relative">
            <span className="block text-xs font-semibold text-slate-600 mb-1">{item.label}</span>
            <div className="relative">
              <pre className="mt-1 bg-slate-800 text-slate-100 rounded-lg p-3 text-sm font-mono overflow-x-auto whitespace-pre-wrap pr-16">
                {item.text}
              </pre>
              <button
                onClick={() => handleCopy(item.text)}
                className="absolute cursor-pointer top-2 right-2 rounded bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-700 transition"
                title={`Copy ${item.label}`}
              >
                Copy
              </button>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="text-xs text-slate-500 italic">No copyable text provided.</div>
        )}
      </div>
    </div>
  );
};
