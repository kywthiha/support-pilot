import React, { useRef, useCallback } from "react";

/**
 * Robust PCM audio player for Gemini Live API responses.
 *
 * Pipeline: base64 → Uint8Array → Int16 PCM → Float32 → AudioBuffer → gapless playback.
 *
 * Handles:
 *  - Standard AND URL-safe base64 (- _ vs + /)
 *  - Missing padding
 *  - Graceful error recovery (skips bad chunks instead of crashing)
 */

const SAMPLE_RATE = 24_000;
type AudioContextCtor = typeof AudioContext;
type WindowWithWebkitAudioContext = Window & {
    webkitAudioContext?: AudioContextCtor;
};

/** Convert any base64 variant to a Uint8Array without throwing */
function decodeBase64(b64: string): Uint8Array | null {
    try {
        // 1. Strip whitespace / newlines
        let clean = b64.replace(/\s/g, "");

        // 2. Convert URL-safe chars → standard base64
        clean = clean.replace(/-/g, "+").replace(/_/g, "/");

        // 3. Fix missing padding
        const pad = clean.length % 4;
        if (pad === 2) clean += "==";
        else if (pad === 3) clean += "=";

        // 4. Decode
        const binary = atob(clean);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes;
    } catch {
        console.warn("[AudioPlayer] Failed to decode base64 chunk, skipping.");
        return null;
    }
}

/** Convert Int16 PCM buffer → Float32 samples */
function pcmToFloat32(pcm: Uint8Array): Float32Array {
    const int16 = new Int16Array(
        pcm.buffer,
        pcm.byteOffset,
        pcm.byteLength / 2,
    );
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
    }
    return float32;
}

export interface UseAudioPlayerReturn {
    init: () => void;
    playAudio: (base64Data: string, mimeType: string) => void;
    playRawAudio: (rawBytes: ArrayBuffer, mimeType: string) => void;
    setVolume: (vol: number) => void;
    stop: () => void;
    flush: () => void;
    analyserRef: React.MutableRefObject<AnalyserNode | null>;
}

export const useAudioPlayer = (): UseAudioPlayerReturn => {
    const ctxRef = useRef<AudioContext | null>(null);
    const nextTimeRef = useRef(0);
    const gainRef = useRef<GainNode | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const scheduledSourcesRef = useRef<AudioBufferSourceNode[]>([]);

    /** Create or resume the AudioContext (call inside a user gesture) */
    const init = useCallback(() => {
        if (!ctxRef.current || ctxRef.current.state === "closed") {
            const AC =
                window.AudioContext ||
                (window as WindowWithWebkitAudioContext).webkitAudioContext;
            if (!AC) {
                throw new Error("AudioContext is not supported in this browser.");
            }
            const ctx = new AC({ sampleRate: SAMPLE_RATE });
            ctxRef.current = ctx;

            // AnalyserNode for real-time frequency visualization
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 256; // 128 frequency bins
            analyser.smoothingTimeConstant = 0.6;
            analyserRef.current = analyser;

            // Master gain for volume control
            const gain = ctx.createGain();
            gain.gain.value = 1.0;

            // Chain: source → analyser → gain → destination
            analyser.connect(gain);
            gain.connect(ctx.destination);
            gainRef.current = gain;
        }
        if (ctxRef.current.state === "suspended") {
            ctxRef.current.resume().catch(console.warn);
        }
    }, []);

    /** Get (or create) a ready AudioContext */
    const getCtx = useCallback(() => {
        if (!ctxRef.current || ctxRef.current.state === "closed") {
            init();
        }
        return ctxRef.current!;
    }, [init]);

    /** Get the output node — connect sources to analyser (head of chain) */
    const getOutput = useCallback(() => {
        return analyserRef.current ?? gainRef.current ?? getCtx().destination;
    }, [getCtx]);

    /**
     * Enqueue a base64-encoded PCM chunk for gapless playback.
     * Gracefully skips bad data instead of crashing.
     */
    const playAudio = useCallback(
        (base64Data: string, mimeType: string) => {
            void mimeType;
            // Decode
            const bytes = decodeBase64(base64Data);
            if (!bytes || bytes.length < 2) return; // need at least 1 sample

            const ctx = getCtx();
            const samples = pcmToFloat32(bytes);
            if (samples.length === 0) return;

            // Build AudioBuffer
            const buffer = ctx.createBuffer(1, samples.length, SAMPLE_RATE);
            buffer.copyToChannel(samples as Float32Array<ArrayBuffer>, 0);

            // Schedule gapless playback
            const source = ctx.createBufferSource();
            source.buffer = buffer;
            source.connect(getOutput());

            const now = ctx.currentTime;
            const startTime = Math.max(now, nextTimeRef.current);
            source.start(startTime);

            // Track for flush/interruption
            scheduledSourcesRef.current.push(source);
            source.onended = () => {
                scheduledSourcesRef.current = scheduledSourcesRef.current.filter(s => s !== source);
            };
            nextTimeRef.current = startTime + buffer.duration;
        },
        [getCtx, getOutput],
    );

    /**
     * Enqueue raw PCM bytes (ArrayBuffer) for gapless playback.
     * Used when audio arrives via binary WebSocket frames.
     */
    const playRawAudio = useCallback(
        (rawBytes: ArrayBuffer, mimeType: string) => {
            void mimeType;
            const bytes = new Uint8Array(rawBytes);
            if (bytes.length < 2) return;

            const ctx = getCtx();
            const samples = pcmToFloat32(bytes);
            if (samples.length === 0) return;

            const buffer = ctx.createBuffer(1, samples.length, SAMPLE_RATE);
            buffer.copyToChannel(samples as Float32Array<ArrayBuffer>, 0);

            const source = ctx.createBufferSource();
            source.buffer = buffer;
            source.connect(getOutput());

            const now = ctx.currentTime;
            const startTime = Math.max(now, nextTimeRef.current);
            source.start(startTime);
            nextTimeRef.current = startTime + buffer.duration;

            // Track for flush/interruption
            scheduledSourcesRef.current.push(source);
            source.onended = () => {
                scheduledSourcesRef.current = scheduledSourcesRef.current.filter(s => s !== source);
            };
        },
        [getCtx, getOutput],
    );

    /** Set master volume (0.0 – 1.0) */
    const setVolume = useCallback((vol: number) => {
        if (gainRef.current) {
            gainRef.current.gain.value = Math.max(0, Math.min(1, vol));
        }
    }, []);

    /**
     * Flush all scheduled audio — used for agent interruption.
     * Stops all queued sources and resets the timeline,
     * but keeps the AudioContext alive so playback can resume.
     */
    const flush = useCallback(() => {
        for (const src of scheduledSourcesRef.current) {
            try { src.stop(); } catch { /* already stopped */ }
        }
        scheduledSourcesRef.current = [];
        nextTimeRef.current = 0;
    }, []);

    /** Tear down the AudioContext entirely (disconnect / unmount) */
    const stop = useCallback(() => {
        flush();
        ctxRef.current?.close();
        ctxRef.current = null;
        gainRef.current = null;
        analyserRef.current = null;
    }, [flush]);

    return { init, playAudio, playRawAudio, setVolume, stop, flush, analyserRef };
}
