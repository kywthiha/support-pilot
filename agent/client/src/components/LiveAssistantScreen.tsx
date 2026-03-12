import { useCallback, useEffect, useRef, useState } from "react";
import {
  Monitor,
  Pen,
  Send,
  MonitorOff,
  Headphones,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Video,
  MessageSquare,
  PlusCircle,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { useCamera } from "@/hooks/useCamera";
import { useMicrophone } from "@/hooks/useMicrophone";
import { useLiveSocket } from "@/hooks/useLiveSocket";
import { useSessionTimer } from "@/hooks/useSessionTimer";
import { useIsDesktop } from "@/hooks/useIsDesktop";
import { FooterWaveOverlay } from "./FooterWaveOverlay";
import { SessionIconButton } from "./SessionIconButton";
import { CaptionOverlay } from "./CaptionOverlay";
import { ChatHistoryPanel } from "./ChatHistoryPanel";

export const LiveAssistantScreen: React.FC = () => {
  const isDesktop = useIsDesktop();
  const {
    flush,
    init: initAudio,
    playRawAudio,
    setVolume,
    stop: stopAudio,
    analyserRef: audioAnalyserRef,
  } = useAudioPlayer();
  const [videoTick, setVideoTick] = useState(0);
  const previewRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isTalkingRef = useRef(false);
  const silenceStartRef = useRef<number>(0);

  const {
    lastError,
    connect,
    disconnect,
    newSession,
    retryNow,
    sendAudio,
    sendFrame,
    sendText,
    status,
    agentName,
    userTranscript,
    agentTranscript,
    chatHistory,
    reconnectCountdown,
    reconnectAttempt,
  } = useLiveSocket({
    onAudio: (bytes) => {
      playRawAudio(bytes, "audio/pcm;rate=24000");
    },
    onInterrupted: () => {
      flush();
    },
    onDisconnected: () => {
      flush();
      stopMicrophone();
      isTalkingRef.current = false;
      setIsStreaming(false);
    },
  });

  const isLiveReady = status === "connected";
  const [isStreaming, setIsStreaming] = useState(false);
  const [isTextPopupOpen, setIsTextPopupOpen] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeakerOff, setIsSpeakerOff] = useState(false);
  const [textInput, setTextInput] = useState("");

  const { formatted: sessionTime } = useSessionTimer(isStreaming);

  const {
    captureAsset,
    error: cameraError,
    start: startCamera,
    stop: stopCamera,
    videoRef,
    mode: cameraMode,
  } = useCamera(
    useCallback(
      (bytes: ArrayBuffer) => {
        sendFrame(bytes);
      },
      [sendFrame],
    ),
    useCallback(
      (bytes: ArrayBuffer) => {
        sendFrame(bytes);
      },
      [sendFrame],
    ),
    1,
  );

  const {
    analyserRef: micAnalyserRef,
    start: startMicrophone,
    stop: stopMicrophone,
    toggleEnabled: toggleMic,
    isEnabled: isMicEnabled,
  } = useMicrophone(
    useCallback(
      (buffer) => {
        sendAudio(buffer);
      },
      [sendAudio],
    ),
  );

  const handleStartStream = () => {
    setIsStreaming(true);
    void startCamera(isDesktop ? "screen" : "camera");
    void startMicrophone();
    try {
      initAudio();
    } catch (error) {
      console.warn("Audio Context init blocked:", error);
    }
    connect();
  };

  const handlePauseStream = () => {
    isTalkingRef.current = false;
    silenceStartRef.current = 0;
    setIsStreaming(false);
    stopCamera();
    stopMicrophone();
    flush();
    disconnect();
  };

  const handleToggleMic = () => {
    toggleMic();
    setIsMuted(!isMicEnabled);
  };

  const handleToggleSpeaker = () => {
    const newOff = !isSpeakerOff;
    setIsSpeakerOff(newOff);
    setVolume(newOff ? 0 : 1);
  };

  useEffect(() => {
    return () => {
      stopCamera();
      stopMicrophone();
      stopAudio();
      disconnect();
    };
  }, [disconnect, stopAudio, stopCamera, stopMicrophone]);

  useEffect(() => {
    if (!isLiveReady || !micAnalyserRef.current) {
      return;
    }

    const analyser = micAnalyserRef.current;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let animationFrame = 0;

    const checkAudio = () => {
      animationFrame = window.requestAnimationFrame(checkAudio);
      analyser.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let index = 0; index < dataArray.length; index += 1) {
        sum += dataArray[index];
      }

      const average = sum / dataArray.length;
      if (average > 2) {
        if (!isTalkingRef.current) {
          isTalkingRef.current = true;
        }
        silenceStartRef.current = 0;
      } else if (isTalkingRef.current) {
        if (silenceStartRef.current === 0) {
          silenceStartRef.current = Date.now();
        } else if (Date.now() - silenceStartRef.current > 1200) {
          isTalkingRef.current = false;
          silenceStartRef.current = 0;
          captureAsset();
        }
      }
    };

    checkAudio();
    return () => window.cancelAnimationFrame(animationFrame);
  }, [captureAsset, isLiveReady, micAnalyserRef]);

  useEffect(() => {
    if (!isLiveReady) {
      return;
    }

    const interval = window.setInterval(() => {
      if (isTalkingRef.current) {
        return;
      }
      captureAsset();
    }, 4000);

    return () => window.clearInterval(interval);
  }, [captureAsset, isLiveReady]);

  useEffect(() => {}, [videoRef, videoTick]);

  // Read server-injected config (from /api/config.js → window.__APP_CONFIG__)
  const appConfig = (window as any).__APP_CONFIG__ as
    | { appTitle?: string; agentDisplayName?: string }
    | undefined;

  const displayName =
    agentName || appConfig?.agentDisplayName || "Customer Support AI";

  // Sync document title with server config
  useEffect(() => {
    document.title = appConfig?.appTitle || "Customer Support AI";
  }, [appConfig?.appTitle]);

  const statusLabel =
    status === "connected"
      ? "Live"
      : status === "connecting" || status === "reconnecting"
        ? "Connecting"
        : status === "error"
          ? "Error"
          : "Offline";

  return (
    <div className="fixed inset-0 flex flex-col overflow-hidden bg-gradient-to-br from-slate-50 to-slate-100 font-sans text-slate-800 touch-none">
      {/* ── Top Bar ── */}
      <header className="relative z-20 flex items-center justify-between bg-white/80 backdrop-blur-md px-4 md:px-5 py-3 border-b border-slate-200/80">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
            <Headphones className="h-4 w-4 text-white" />
          </div>
          <span className="text-sm md:text-base font-bold tracking-tight text-slate-900 truncate max-w-[180px] md:max-w-none">
            {displayName}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Session Timer */}
          {isStreaming && (
            <span className="hidden sm:inline text-xs font-mono text-slate-500 bg-slate-100 px-2 py-1 rounded-md">
              {sessionTime}
            </span>
          )}

          {/* Status Pill */}
          <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
            <span
              className={`h-2 w-2 rounded-full ${
                status === "connected"
                  ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]"
                  : status === "connecting" || status === "reconnecting"
                    ? "bg-amber-400 animate-pulse"
                    : status === "error"
                      ? "bg-red-500"
                      : "bg-slate-300"
              }`}
            />
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              {statusLabel}
            </span>
          </div>

          {/* Chat History Toggle */}
          {!isDesktop && (
            <button
              onClick={() => setIsChatOpen(!isChatOpen)}
              className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                isChatOpen
                  ? "bg-indigo-100 text-indigo-600"
                  : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              }`}
              title="Conversation History"
            >
              <MessageSquare className="h-4 w-4" />
              {chatHistory.length > 0 && !isChatOpen && (
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[9px] font-bold text-white">
                  {chatHistory.length > 9 ? "9+" : chatHistory.length}
                </span>
              )}
            </button>
          )}

          {/* New Session Button */}
          <button
            onClick={() => {
              if (
                window.confirm(
                  "Start a new session? This will clear the current chat history.",
                )
              ) {
                handlePauseStream();
                newSession();
              }
            }}
            className="flex h-5 w-5 items-center justify-center rounded-lg text-slate-300 opacity-30 transition-all hover:bg-slate-100 hover:text-slate-500 hover:opacity-100 ml-1"
            title="Start New Session"
          >
            <PlusCircle className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      {/* ── Main Content ── */}
      <div className="relative flex flex-1 min-h-0 overflow-hidden">
        <main
          ref={previewRef}
          className="relative flex-1 min-h-0 overflow-hidden"
        >
          {/* Connecting animation */}
          {status === "connecting" && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 bg-white/80 backdrop-blur-sm fade-in">
              <Loader2 className="h-10 w-10 text-indigo-500 animate-spin" />
              <p className="text-sm font-semibold text-slate-600">
                Connecting to agent...
              </p>
            </div>
          )}

          {/* Reconnecting banner */}
          {status === "reconnecting" && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 bg-white/80 backdrop-blur-sm fade-in">
              <RefreshCw className="h-10 w-10 text-amber-500 animate-spin" />
              <p className="text-sm font-semibold text-slate-600">
                Reconnecting
                {reconnectCountdown > 0 ? ` in ${reconnectCountdown}s` : "..."}
              </p>
              <p className="text-xs text-slate-400">
                Attempt {reconnectAttempt} of 6
              </p>
              <button
                onClick={retryNow}
                className="mt-1 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-md hover:bg-indigo-700 active:scale-95 transition-all"
              >
                Retry Now
              </button>
            </div>
          )}

          {isStreaming ? (
            <>
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                onLoadedMetadata={() => setVideoTick((value) => value + 1)}
                className={`h-full w-full object-contain ${cameraMode === "screen" ? "bg-slate-900" : "bg-black"}`}
              />
              <canvas
                ref={canvasRef}
                className="pointer-events-none absolute inset-0 h-full w-full"
              />
              <CaptionOverlay
                userTranscript={userTranscript}
                agentTranscript={agentTranscript}
              />
            </>
          ) : (
            !["connecting", "reconnecting"].includes(status) && (
              <div className="flex h-full flex-col items-center justify-center gap-6 px-6 text-center">
                {/* Decorative background */}
                <div className="pointer-events-none absolute inset-0 overflow-hidden">
                  <div className="absolute left-1/2 top-1/3 -translate-x-1/2 -translate-y-1/2 h-[400px] w-[400px] rounded-full bg-indigo-100/60 blur-3xl" />
                  <div className="absolute right-1/4 bottom-1/4 h-[300px] w-[300px] rounded-full bg-violet-100/50 blur-3xl" />
                </div>

                <div className="relative">
                  <div className="flex h-24 w-24 items-center justify-center rounded-3xl bg-white border border-slate-200 shadow-lg shadow-indigo-100/50">
                    {isDesktop ? (
                      <Monitor className="h-12 w-12 text-indigo-500" />
                    ) : (
                      <Video className="h-12 w-12 text-indigo-500" />
                    )}
                  </div>
                  <div className="absolute -bottom-1 -right-1 flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 border-2 border-white shadow-md">
                    <Headphones className="h-4 w-4 text-white" />
                  </div>
                </div>
                <div className="relative space-y-2">
                  <h2 className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">
                    {isDesktop ? "Share Your Screen" : "Start Camera"}
                  </h2>
                  <p className="max-w-sm text-sm text-slate-500 leading-relaxed">
                    {isDesktop
                      ? "Start a live session and our AI assistant will see your screen, listen to you, and guide you step by step with voice."
                      : "Start a live session and our AI assistant will see through your camera, listen to you, and guide you step by step with voice."}
                  </p>
                </div>
                <button
                  onClick={handleStartStream}
                  className="relative mt-2 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-6 md:px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200/50 transition-all hover:bg-indigo-700 hover:shadow-xl hover:shadow-indigo-200/60 active:scale-[0.98]"
                >
                  {isDesktop ? (
                    <Monitor className="h-4 w-4" />
                  ) : (
                    <Video className="h-4 w-4" />
                  )}
                  {isDesktop ? "Start Screen Share" : "Start Camera"}
                </button>
              </div>
            )
          )}
        </main>

        {/* Chat History Panel */}
        <ChatHistoryPanel
          messages={chatHistory}
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          isDesktop={isDesktop}
        />
      </div>

      {/* ── Bottom Control Bar ── */}
      <footer className="relative z-30 bg-white/80 backdrop-blur-md border-t border-slate-200/80 px-3 md:px-4 pt-2 pb-5 md:pb-6">
        {lastError && status !== "reconnecting" ? (
          <div className="fade-in mb-2 flex w-full justify-center">
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-xs font-semibold text-red-600 shadow-sm">
              {lastError}
            </div>
          </div>
        ) : null}

        {!isStreaming && (
          <CaptionOverlay
            userTranscript={userTranscript}
            agentTranscript={agentTranscript}
          />
        )}

        <div className="z-40 w-full max-w-3xl mx-auto fade-in">
          <div className="relative flex items-center gap-2 md:gap-3 rounded-2xl border border-slate-200/80 bg-white p-2 md:p-2.5 shadow-lg shadow-slate-200/50">
            {isLiveReady && (
              <div className="relative flex gap-1.5 md:gap-2">
                {/* Text input button */}
                <button
                  onClick={() => setIsTextPopupOpen(!isTextPopupOpen)}
                  className="flex h-10 w-10 md:h-11 md:w-11 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500 transition-all hover:bg-slate-100 hover:text-slate-700 hover:border-slate-300 active:scale-95"
                  title="Send Text Message"
                >
                  <Pen className="h-4 w-4" />
                </button>

                {/* Screen share toggle (desktop only) */}
                {isStreaming && isDesktop && (
                  <button
                    onClick={() => {
                      void startCamera(
                        cameraMode === "camera" ? "screen" : "camera",
                      );
                    }}
                    className={`flex h-10 w-10 md:h-11 md:w-11 items-center justify-center rounded-xl border transition-all active:scale-95 ${
                      cameraMode === "screen"
                        ? "border-indigo-200 bg-indigo-50 text-indigo-600 hover:bg-indigo-100"
                        : "border-slate-200 bg-slate-50 text-slate-500 hover:bg-slate-100"
                    }`}
                    title={
                      cameraMode === "camera"
                        ? "Share Screen"
                        : "Stop Screen Share"
                    }
                  >
                    {cameraMode === "camera" ? (
                      <Monitor className="h-4 w-4" />
                    ) : (
                      <MonitorOff className="h-4 w-4" />
                    )}
                  </button>
                )}

                {/* Mic mute */}
                <button
                  onClick={handleToggleMic}
                  className={`flex h-10 w-10 md:h-11 md:w-11 items-center justify-center rounded-xl border transition-all active:scale-95 ${
                    isMuted
                      ? "border-red-200 bg-red-50 text-red-500 hover:bg-red-100"
                      : "border-slate-200 bg-slate-50 text-slate-500 hover:bg-slate-100"
                  }`}
                  title={isMuted ? "Unmute Microphone" : "Mute Microphone"}
                >
                  {isMuted ? (
                    <MicOff className="h-4 w-4" />
                  ) : (
                    <Mic className="h-4 w-4" />
                  )}
                </button>

                {/* Speaker toggle */}
                <button
                  onClick={handleToggleSpeaker}
                  className={`flex h-10 w-10 md:h-11 md:w-11 items-center justify-center rounded-xl border transition-all active:scale-95 ${
                    isSpeakerOff
                      ? "border-red-200 bg-red-50 text-red-500 hover:bg-red-100"
                      : "border-slate-200 bg-slate-50 text-slate-500 hover:bg-slate-100"
                  }`}
                  title={isSpeakerOff ? "Unmute Speaker" : "Mute Speaker"}
                >
                  {isSpeakerOff ? (
                    <VolumeX className="h-4 w-4" />
                  ) : (
                    <Volume2 className="h-4 w-4" />
                  )}
                </button>
              </div>
            )}

            <FooterWaveOverlay
              userAnalyserRef={micAnalyserRef}
              agentAnalyserRef={audioAnalyserRef}
            />
            <SessionIconButton
              isStreaming={isStreaming}
              onClick={isStreaming ? handlePauseStream : handleStartStream}
            />
          </div>
        </div>
      </footer>

      {/* ── Error overlay ── */}
      {cameraError ? (
        <div className="pointer-events-auto absolute inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6 backdrop-blur-sm fade-in">
          <div className="flex w-full max-w-sm flex-col items-center rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-2xl">
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-50 border border-red-100">
              <Monitor className="h-8 w-8 text-red-500" />
            </div>
            <h3 className="mb-2 text-xl font-bold tracking-tight text-slate-900">
              Screen Access Required
            </h3>
            <p className="mb-8 text-sm leading-relaxed text-slate-500">
              {cameraError}. Please allow screen sharing access in your browser
              to continue using Customer Support AI.
            </p>
            <button
              className="flex h-12 w-full items-center justify-center rounded-xl bg-indigo-600 text-base font-bold text-white hover:bg-indigo-700 shadow-lg shadow-indigo-200/50 transition-all active:scale-[0.98]"
              onClick={() => window.location.reload()}
            >
              Reload App
            </button>
          </div>
        </div>
      ) : null}

      {/* ── Text input popup ── */}
      {isTextPopupOpen && (
        <div className="pointer-events-auto absolute inset-0 z-[100] flex items-center justify-center bg-slate-900/30 p-6 backdrop-blur-sm fade-in">
          <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-3xl border border-slate-200 bg-white p-8 shadow-2xl">
            <h3 className="text-lg font-bold tracking-tight text-slate-900 w-full text-center">
              Send a Message
            </h3>
            <div className="flex w-full items-center gap-2">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && textInput.trim()) {
                    sendText(textInput.trim());
                    setTextInput("");
                    setIsTextPopupOpen(false);
                  }
                }}
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 transition-all"
                placeholder="Type a message..."
                autoFocus
              />
              <button
                onClick={() => {
                  if (textInput.trim()) {
                    sendText(textInput.trim());
                    setTextInput("");
                    setIsTextPopupOpen(false);
                  }
                }}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition-all hover:bg-indigo-700 shadow-md active:scale-95"
              >
                <Send className="h-5 w-5" />
              </button>
            </div>
            <button
              onClick={() => setIsTextPopupOpen(false)}
              className="text-sm font-medium text-slate-400 hover:text-slate-600 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
