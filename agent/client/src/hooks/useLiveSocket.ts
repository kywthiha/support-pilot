import { useCallback, useEffect, useRef, useState } from "react";
import { buildBinaryMessage, MSG_TYPE } from "@/lib/binary";
import { generateUUID } from "@/lib/uuid";

type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

export interface Citation {
  id: string;
  hazard_family: string;
  source_title: string;
  source_url: string;
  rule_text: string;
  recommended_action: string;
  keywords?: string[];
}

export type ToolResponseEntry = {
  name: string;
  response: {
    status: string;
    tool_name: string;
    timestamp?: string;
    data?: Record<string, unknown> | null;
    error?: { error_code: string; error_message: string } | null;
  };
};

export type ChatMessageType =
  | "text"
  | "input_transcription"
  | "output_transcription"
  | "tool_response"
  | "guide"
  | "error"
  | "system";

export interface ChatMessage {
  id: string;
  text: string;
  type: ChatMessageType;
  isAgent: boolean;
  timestamp: number;
  isPartial?: boolean;
  toolData?: any;
  isGuide?: boolean;
}

function cleanCJKSpaces(text: string): string {
  return text.replace(/(\S)(\s+)(\S)/g, (match, char1, _spaces, char2) => {
    const isCJK1 = /[\u3000-\u9faf\uff00-\uffef]/.test(char1);
    const isCJK2 = /[\u3000-\u9faf\uff00-\uffef]/.test(char2);
    if (isCJK1 && isCJK2) return char1 + char2;
    return match;
  });
}

type ServerMessage = {
  type?: "ready" | "error" | "tool_response";
  sessionId?: string;
  agentName?: string;
  message?: string;
  code?: string;
  turnComplete?: boolean;
  interrupted?: boolean;
  responses?: ToolResponseEntry[];
  inputTranscription?: {
    text: string;
    finished: boolean;
  };
  outputTranscription?: {
    text: string;
    finished: boolean;
  };
  content?: {
    parts: Array<{
      text?: string;
      thought?: boolean;
    }>;
  };
  partial?: boolean;
};

const WS_BASE =
  import.meta.env.VITE_WS_URL ||
  (import.meta.env.DEV
    ? "ws://localhost:8000"
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`);

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 8000;
const RECONNECT_MAX_ATTEMPTS = 6;

function nextTranscriptChunk(
  previous: string,
  nextChunk: string,
  wasFinal: boolean,
): string {
  if (!nextChunk.trim()) {
    return previous;
  }
  return wasFinal ? nextChunk : `${previous}${nextChunk}`;
}

export interface UseLiveSocketOptions {
  onAudio: (bytes: ArrayBuffer, mimeType: string) => void;
  onInterrupted: () => void;
  onDisconnected?: () => void;
}

export interface UseLiveSocketReturn {
  connect: () => void;
  disconnect: () => void;
  newSession: () => void;
  retryNow: () => void;
  status: ConnectionStatus;
  sessionId: string | null;
  agentName: string | null;
  toolResponses: ToolResponseEntry[];
  userTranscript: string;
  agentTranscript: string;
  chatHistory: ChatMessage[];
  lastError: string | null;
  reconnectCountdown: number;
  reconnectAttempt: number;
  sendAudio: (buffer: ArrayBuffer) => void;
  sendFrame: (bytes: ArrayBuffer) => void;
  sendText: (text: string) => void;
}

export const useLiveSocket = (options: UseLiveSocketOptions): UseLiveSocketReturn => {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const agentTranscriptFinalRef = useRef(true);
  const userTranscriptFinalRef = useRef(true);
  const hasOutputTranscriptionRef = useRef(false);
  const audioHandlerRef = useRef(options.onAudio);
  const interruptedHandlerRef = useRef(options.onInterrupted);
  const disconnectHandlerRef = useRef(options.onDisconnected);
  const sessionIdRef = useRef<string | null>(null);

  // Track active bubbles
  const activeMsgIdRef = useRef<string | null>(null);
  const activeInputTranscriptIdRef = useRef<string | null>(null);
  const activeOutputTranscriptIdRef = useRef<string | null>(null);
  const inputTranscriptionFinishedRef = useRef(false);

  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [agentName, setAgentName] = useState<string | null>(null);
  const [toolResponses, setToolResponses] = useState<ToolResponseEntry[]>([]);
  const [userTranscript, setUserTranscript] = useState("");
  const [agentTranscript, setAgentTranscript] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);
  const [reconnectCountdown, setReconnectCountdown] = useState(0);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  const clearCountdown = useCallback(() => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
    setReconnectCountdown(0);
  }, []);

  const resetConversationState = useCallback(() => {
    setToolResponses([]);
    setUserTranscript("");
    setAgentTranscript("");
    userTranscriptFinalRef.current = true;
    agentTranscriptFinalRef.current = true;
    hasOutputTranscriptionRef.current = false;
    activeMsgIdRef.current = null;
    activeInputTranscriptIdRef.current = null;
    activeOutputTranscriptIdRef.current = null;
    inputTranscriptionFinishedRef.current = false;
  }, []);

  useEffect(() => {
    audioHandlerRef.current = options.onAudio;
    interruptedHandlerRef.current = options.onInterrupted;
    disconnectHandlerRef.current = options.onDisconnected;
  }, [options.onAudio, options.onDisconnected, options.onInterrupted]);

  const handleMessage = useCallback(
    (raw: ServerMessage) => {
      if (raw.type === "ready") {
        resetConversationState();
        setSessionId(raw.sessionId || null);
        if (raw.agentName) {
          setAgentName(raw.agentName);
        }
        setStatus("connected");
        setLastError(null);
        clearCountdown();
        setReconnectAttempt(0);
        return;
      }

      if (raw.type === "error") {
        setLastError(raw.message || "Unknown error");
        return;
      }

      // Handle tool responses from server
      if (raw.type === "tool_response" && raw.responses) {
        for (const tr of raw.responses) {
          if (
            tr.name === "send_copy_text" &&
            tr.response?.status === "success" &&
            tr.response?.data
          ) {
            const data = tr.response.data as Record<string, unknown>;
            const items = data.items as Array<{ label: string, text: string }>;
            const explanation = data.explanation as string;

            if (items && items.length > 0) {
              setChatHistory((prev) => [
                ...prev,
                {
                  id: generateUUID(),
                  text: explanation || "Here is the information:",
                  type: "guide",
                  isAgent: true,
                  isGuide: true,
                  timestamp: Date.now(),
                  toolData: data,
                },
              ]);
            }
          }
        }
        setToolResponses((prev) => [...prev, ...raw.responses!]);
        return;
      }

      if (raw.turnComplete) {
        setChatHistory((prev) =>
          prev.map((msg) =>
            msg.id === activeMsgIdRef.current ||
              msg.id === activeInputTranscriptIdRef.current ||
              msg.id === activeOutputTranscriptIdRef.current
              ? { ...msg, isPartial: false }
              : msg
          )
        );
        activeMsgIdRef.current = null;
        activeOutputTranscriptIdRef.current = null;
        inputTranscriptionFinishedRef.current = false;
        hasOutputTranscriptionRef.current = false;
        return;
      }

      if (raw.interrupted) {
        interruptedHandlerRef.current();
        setAgentTranscript("");
        agentTranscriptFinalRef.current = true;
        setChatHistory((prev) =>
          prev.map((msg) =>
            msg.id === activeMsgIdRef.current ||
              msg.id === activeOutputTranscriptIdRef.current
              ? { ...msg, isPartial: false, text: msg.text + " [Interrupted]" }
              : msg
          )
        );
        activeMsgIdRef.current = null;
        activeOutputTranscriptIdRef.current = null;
        inputTranscriptionFinishedRef.current = false;
        hasOutputTranscriptionRef.current = false;
        return;
      }

      if (raw.inputTranscription?.text) {
        const chunk = raw.inputTranscription.text;
        const isFinished = raw.inputTranscription.finished;

        setUserTranscript((previous) =>
          nextTranscriptChunk(previous, chunk, userTranscriptFinalRef.current)
        );
        userTranscriptFinalRef.current = isFinished;

        if (chunk && !inputTranscriptionFinishedRef.current) {
          if (!activeInputTranscriptIdRef.current) {
            const newId = generateUUID();
            activeInputTranscriptIdRef.current = newId;
            setChatHistory((prev) => [
              ...prev,
              {
                id: newId,
                text: cleanCJKSpaces(chunk),
                type: "input_transcription",
                isAgent: false,
                timestamp: Date.now(),
                isPartial: !isFinished,
              },
            ]);
          } else if (!activeOutputTranscriptIdRef.current && !activeMsgIdRef.current) {
            setChatHistory((prev) =>
              prev.map((msg) => {
                if (msg.id === activeInputTranscriptIdRef.current) {
                  return {
                    ...msg,
                    text: cleanCJKSpaces(isFinished ? chunk : msg.text + chunk),
                    isPartial: !isFinished,
                  };
                }
                return msg;
              })
            );
          }
          if (isFinished) {
            activeInputTranscriptIdRef.current = null;
            inputTranscriptionFinishedRef.current = true;
          }
        }
      }

      if (raw.outputTranscription?.text) {
        hasOutputTranscriptionRef.current = true;
        const chunk = raw.outputTranscription.text;
        const isFinished = raw.outputTranscription.finished;

        setAgentTranscript((previous) =>
          nextTranscriptChunk(previous, chunk, agentTranscriptFinalRef.current)
        );
        agentTranscriptFinalRef.current = isFinished;

        if (chunk) {
          if (activeInputTranscriptIdRef.current && !activeOutputTranscriptIdRef.current) {
            setChatHistory((prev) =>
              prev.map((msg) =>
                msg.id === activeInputTranscriptIdRef.current
                  ? { ...msg, isPartial: false }
                  : msg
              )
            );
            activeInputTranscriptIdRef.current = null;
            inputTranscriptionFinishedRef.current = true;
          }

          if (!activeOutputTranscriptIdRef.current) {
            const newId = generateUUID();
            activeOutputTranscriptIdRef.current = newId;
            setChatHistory((prev) => [
              ...prev,
              {
                id: newId,
                text: cleanCJKSpaces(chunk),
                type: "output_transcription",
                isAgent: true,
                timestamp: Date.now(),
                isPartial: !isFinished,
              },
            ]);
          } else {
            setChatHistory((prev) =>
              prev.map((msg) => {
                if (msg.id === activeOutputTranscriptIdRef.current) {
                  return {
                    ...msg,
                    text: cleanCJKSpaces(isFinished ? chunk : msg.text + chunk),
                    isPartial: !isFinished,
                  };
                }
                return msg;
              })
            );
          }
          if (isFinished) {
            activeOutputTranscriptIdRef.current = null;
          }
        }
      }

      if (raw.content?.parts) {
        if (activeInputTranscriptIdRef.current && !activeMsgIdRef.current && !activeOutputTranscriptIdRef.current) {
          setChatHistory((prev) =>
            prev.map((msg) =>
              msg.id === activeInputTranscriptIdRef.current
                ? { ...msg, isPartial: false }
                : msg
            )
          );
          activeInputTranscriptIdRef.current = null;
          inputTranscriptionFinishedRef.current = true;
        }

        for (const part of raw.content.parts) {
          if (part.text && !part.thought) {
            if (!raw.partial && hasOutputTranscriptionRef.current) {
              continue;
            }

            setAgentTranscript((previous) =>
              nextTranscriptChunk(previous, part.text!, agentTranscriptFinalRef.current)
            );
            agentTranscriptFinalRef.current = !raw.partial;

            if (!activeMsgIdRef.current) {
              const newId = generateUUID();
              activeMsgIdRef.current = newId;
              setChatHistory((prev) => [
                ...prev,
                {
                  id: newId,
                  text: cleanCJKSpaces(part.text!),
                  type: "text",
                  isAgent: true,
                  timestamp: Date.now(),
                  isPartial: !!raw.partial,
                },
              ]);
            } else {
              setChatHistory((prev) =>
                prev.map((msg) => {
                  if (msg.id === activeMsgIdRef.current) {
                    return {
                      ...msg,
                      text: cleanCJKSpaces(msg.text + part.text!),
                      isPartial: !!raw.partial,
                    };
                  }
                  return msg;
                })
              );
            }
          }
        }
      }
    },
    [clearCountdown, resetConversationState],
  );

  const connect = useCallback(
    function connectSocket() {
      intentionalCloseRef.current = false;
      clearCountdown();

      if (
        wsRef.current &&
        (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      if (wsRef.current?.readyState === WebSocket.CLOSING) {
        wsRef.current = null;
      }

      const isReconnect = reconnectAttemptsRef.current > 0;
      setStatus(isReconnect ? "reconnecting" : "connecting");

      let userId = localStorage.getItem("live_user_id");
      if (!userId) {
        userId = generateUUID();
        localStorage.setItem("live_user_id", userId);
      }

      if (!sessionIdRef.current) {
        sessionIdRef.current = generateUUID();
      }
      const newSessionId = sessionIdRef.current;

      const ws = new WebSocket(`${WS_BASE}/ws/${userId}/${newSessionId}`);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0;
        setReconnectAttempt(0);
        setStatus("connected");
        setLastError(null);
        clearCountdown();
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          audioHandlerRef.current(event.data, "audio/pcm;rate=24000");
          return;
        }

        if (typeof event.data !== "string") {
          return;
        }

        try {
          handleMessage(JSON.parse(event.data) as ServerMessage);
        } catch {
          setLastError("Received an invalid server message.");
        }
      };

      ws.onclose = () => {
        if (wsRef.current !== ws) {
          return;
        }

        wsRef.current = null;
        setSessionId(null);
        disconnectHandlerRef.current?.();

        if (intentionalCloseRef.current) {
          setStatus("disconnected");
          return;
        }
        if (reconnectAttemptsRef.current >= RECONNECT_MAX_ATTEMPTS) {
          setStatus("error");
          setLastError("The live connection closed.");
          return;
        }
        const delay = Math.min(
          RECONNECT_BASE_MS * 2 ** reconnectAttemptsRef.current,
          RECONNECT_MAX_MS,
        );
        reconnectAttemptsRef.current += 1;
        setReconnectAttempt(reconnectAttemptsRef.current);
        setStatus("reconnecting");

        // Start countdown
        const delaySecs = Math.ceil(delay / 1000);
        setReconnectCountdown(delaySecs);
        countdownTimerRef.current = setInterval(() => {
          setReconnectCountdown((prev) => {
            if (prev <= 1) {
              clearInterval(countdownTimerRef.current!);
              countdownTimerRef.current = null;
              return 0;
            }
            return prev - 1;
          });
        }, 1000);

        reconnectTimerRef.current = setTimeout(() => {
          connectSocket();
        }, delay);
      };

      ws.onerror = () => {
        setLastError("The live connection encountered an error.");
      };
    },
    [clearCountdown, handleMessage],
  );

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearCountdown();
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
    sessionIdRef.current = null;
    setSessionId(null);
    setStatus("disconnected");
    setReconnectAttempt(0);
  }, [clearCountdown]);

  const newSession = useCallback(() => {
    disconnect();
    setSessionId(null);
    setChatHistory([]);
    setToolResponses([]);
    resetConversationState();
  }, [disconnect, resetConversationState]);

  const retryNow = useCallback(() => {
    clearCountdown();
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptsRef.current = 0;
    setReconnectAttempt(0);
    connect();
  }, [clearCountdown, connect]);

  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      clearCountdown();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [clearCountdown]);

  const sendJson = useCallback((payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      return;
    }
    wsRef.current.send(JSON.stringify(payload));
  }, []);

  const sendAudio = useCallback((buffer: ArrayBuffer) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      return;
    }
    const message = buildBinaryMessage(MSG_TYPE.AUDIO, buffer);
    wsRef.current.send(message);
  }, []);

  const sendFrame = useCallback(
    (bytes: ArrayBuffer) => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) {
        return;
      }
      const message = buildBinaryMessage(MSG_TYPE.VIDEO, bytes);
      wsRef.current.send(message);
    },
    [],
  );

  const sendText = useCallback((text: string) => {
    sendJson({ type: "text", text });
    setChatHistory((prev) => [
      ...prev,
      {
        id: generateUUID(),
        text,
        type: "text",
        isAgent: false,
        timestamp: Date.now(),
        isPartial: false,
      },
    ]);
  }, [sendJson]);

  return {
    connect,
    disconnect,
    newSession,
    retryNow,
    status,
    sessionId,
    agentName,
    toolResponses,
    userTranscript,
    agentTranscript,
    chatHistory,
    lastError,
    reconnectCountdown,
    reconnectAttempt,
    sendAudio,
    sendFrame,
    sendText,
  };
}
