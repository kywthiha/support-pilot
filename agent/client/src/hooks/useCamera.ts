import React, { useRef, useState, useCallback, useEffect } from "react";

export type FrameHandler = (bytes: ArrayBuffer, mimeType: string) => void;

export interface UseCameraReturn {
    isActive: boolean;
    error: string | null;
    start: (mode?: 'camera' | 'screen') => Promise<void>;
    stop: () => void;
    toggle: () => void;
    captureAsset: () => Promise<void>;
    videoRef: React.MutableRefObject<HTMLVideoElement | null>;
    mode: 'camera' | 'screen';
}

export const useCamera = (
    onFrame: FrameHandler,
    onCapture?: FrameHandler,
    fps: number = 1,
    jpegQuality: number = 0.85
): UseCameraReturn => {
    const [isActive, setIsActive] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [mode, setMode] = useState<'camera' | 'screen'>('camera');

    const streamRef = useRef<MediaStream | null>(null);
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const intervalRef = useRef<number | null>(null);

    const MAX_DIM = 768;

    /** Capture one frame */
    const captureFrame = useCallback(async () => {
        const video = videoRef.current;
        if (!video || video.videoWidth === 0) return null;

        if (!canvasRef.current) {
            canvasRef.current = document.createElement("canvas");
        }

        const canvas = canvasRef.current;

        const scale = Math.min(
            1,
            MAX_DIM / Math.max(video.videoWidth, video.videoHeight)
        );

        const w = Math.round(video.videoWidth * scale);
        const h = Math.round(video.videoHeight * scale);

        if (canvas.width !== w) canvas.width = w;
        if (canvas.height !== h) canvas.height = h;

        const ctx = canvas.getContext("2d");
        if (!ctx) return null;

        ctx.drawImage(video, 0, 0, w, h);

        return new Promise<{ bytes: ArrayBuffer; mimeType: string } | null>(
            (resolve) => {
                canvas.toBlob(
                    async (blob) => {
                        if (!blob) return resolve(null);

                        const buffer = await blob.arrayBuffer();

                        resolve({
                            bytes: buffer,
                            mimeType: "image/jpeg",
                        });
                    },
                    "image/jpeg",
                    jpegQuality
                );
            }
        );
    }, [jpegQuality]);

    /** Frame loop */
    const captureStreamFrame = useCallback(async () => {
        const frame = await captureFrame();

        if (frame) {
            onFrame(frame.bytes, frame.mimeType);
        }
    }, [captureFrame, onFrame]);

    /** Capture one asset frame manually */
    const captureAsset = useCallback(async () => {
        const frame = await captureFrame();

        if (frame && onCapture) {
            onCapture(frame.bytes, frame.mimeType);
        }
    }, [captureFrame, onCapture]);

    /** Stop camera */
    const stop = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }

        streamRef.current?.getTracks().forEach((track) => track.stop());

        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }

        streamRef.current = null;

        setIsActive(false);
    }, []);

    /** Start camera or screen share */
    const start = useCallback(async (requestedMode: 'camera' | 'screen' = 'camera') => {
        try {
            setError(null);

            // Stop existing if switching modes or restarting
            if (isActive) {
                stop();
            }

            let stream: MediaStream;

            if (requestedMode === 'screen') {
                stream = await navigator.mediaDevices.getDisplayMedia({
                    video: true,
                    audio: false,
                });
            } else {
                stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        width: { ideal: 768 },
                        height: { ideal: 768 },
                        facingMode: { ideal: "environment" },
                    },
                    audio: false,
                });
            }

            streamRef.current = stream;

            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
            }

            const interval = 1000 / fps;

            intervalRef.current = window.setInterval(
                captureStreamFrame,
                interval
            );

            setIsActive(true);
            setMode(requestedMode);
            
            // Handle native stop (e.g. user clicked "Stop sharing" in browser UI)
            if (requestedMode === 'screen') {
                const videoTrack = stream.getVideoTracks()[0];
                if (videoTrack) {
                    videoTrack.onended = () => {
                        stop();
                    };
                }
            }
            
        } catch (err) {
            console.error("Camera/Screen error:", err);
            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to access media device"
            );
        }
    }, [fps, captureStreamFrame, isActive, stop]);

    /** Toggle camera */
    const toggle = useCallback(() => {
        if (isActive) stop();
        else start();
    }, [isActive, start, stop]);

    /** Sync stream to video element whenever it mounts/unmounts after render */
    useEffect(() => {
        if (isActive && videoRef.current && streamRef.current) {
            if (videoRef.current.srcObject !== streamRef.current) {
                videoRef.current.srcObject = streamRef.current;
                videoRef.current.play().catch(e => console.error("Play error:", e));
            }
        }
    });

    /** Cleanup */
    useEffect(() => {
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
            streamRef.current?.getTracks().forEach((t) => t.stop());
        };
    }, []);

    return {
        isActive,
        error,
        start,
        stop,
        toggle,
        captureAsset,
        videoRef,
        mode,
    };
}