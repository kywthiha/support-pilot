import React, { useRef, useState, useCallback } from "react";

/**
 * Captures microphone audio as 16 kHz PCM Int16 and sends
 * binary frames via the provided callback.
 *
 * Also exposes an AnalyserNode for real-time frequency visualization.
 */
export interface UseMicrophoneReturn {
    isRecording: boolean;
    isEnabled: boolean;
    start: () => Promise<boolean>;
    stop: () => void;
    toggle: () => void;
    toggleEnabled: () => void;
    analyserRef: React.RefObject<AnalyserNode | null>;
}

// Convert Float32 samples to 16-bit PCM
function convertFloat32ToPCM(inputData: Float32Array): ArrayBuffer {
    const pcm16 = new Int16Array(inputData.length);
    for (let i = 0; i < inputData.length; i++) {
        // Web Audio API provides Float32 samples in range [-1.0, 1.0]
        pcm16[i] = inputData[i] * 0x7fff;
    }
    return pcm16.buffer;
}

export const useMicrophone = (onPCMData: (buffer: ArrayBuffer) => void): UseMicrophoneReturn => {
    const [isRecording, setIsRecording] = useState(false);
    const [isEnabled, setIsEnabled] = useState(true);
    const ctxRef = useRef<AudioContext | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const workletRef = useRef<AudioWorkletNode | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);

    const applyEnabledState = useCallback((enabled: boolean) => {
        streamRef.current?.getAudioTracks().forEach((track) => {
            track.enabled = enabled;
        });
    }, []);

    const start = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });

            stream.getAudioTracks().forEach((track) => {
                track.enabled = true;
            });

            // 16kHz matches Live API input spec — no resampling needed
            const ctx = new AudioContext({ sampleRate: 16000 });
            await ctx.audioWorklet.addModule("/pcm-processor.js");

            const source = ctx.createMediaStreamSource(stream);
            const worklet = new AudioWorkletNode(ctx, "pcm-processor");

            worklet.port.onmessage = (ev: MessageEvent<Float32Array>) => {
                const pcmData = convertFloat32ToPCM(ev.data);
                onPCMData(pcmData);
            };

            // AnalyserNode for real-time frequency data
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 256; // 128 frequency bins
            analyser.smoothingTimeConstant = 0.6;

            source.connect(worklet);
            source.connect(analyser);
            // Don't connect to destination — we don't want to hear ourselves

            ctxRef.current = ctx;
            streamRef.current = stream;
            workletRef.current = worklet;
            analyserRef.current = analyser;
            setIsRecording(true);
            setIsEnabled(true);
            return true;
        } catch (err) {
            console.error("Microphone error:", err);
            return false;
        }
    }, [onPCMData]);

    const stop = useCallback(() => {
        analyserRef.current?.disconnect();
        workletRef.current?.disconnect();
        streamRef.current?.getTracks().forEach((t) => t.stop());
        ctxRef.current?.close();
        analyserRef.current = null;
        workletRef.current = null;
        streamRef.current = null;
        ctxRef.current = null;
        setIsRecording(false);
        setIsEnabled(true);
    }, []);

    const toggle = useCallback(() => {
        if (isRecording) stop();
        else start();
    }, [isRecording, start, stop]);

    const toggleEnabled = useCallback(() => {
        setIsEnabled((current) => {
            const next = !current;
            applyEnabledState(next);
            return next;
        });
    }, [applyEnabledState]);

    return { isRecording, isEnabled, start, stop, toggle, toggleEnabled, analyserRef };
}
