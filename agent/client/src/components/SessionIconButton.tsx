import React from "react";
import { Play, Square } from "lucide-react";

export interface SessionIconButtonProps {
  isStreaming: boolean;
  onClick: () => void;
}

export const SessionIconButton: React.FC<SessionIconButtonProps> = ({
  isStreaming,
  onClick,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl shadow-lg transition-all duration-200 active:scale-95 ${
        isStreaming
          ? "bg-red-500 hover:bg-red-600 shadow-red-200/60"
          : "bg-indigo-600 hover:bg-indigo-700 shadow-indigo-200/60"
      }`}
    >
      <div className="flex items-center justify-center text-white">
        {isStreaming ? (
          <Square className="h-5 w-5 fill-current" />
        ) : (
          <Play className="h-6 w-6 fill-current ml-0.5" />
        )}
      </div>
    </button>
  );
};
