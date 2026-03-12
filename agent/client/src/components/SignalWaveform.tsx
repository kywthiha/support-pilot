import React, { type MutableRefObject, useEffect, useRef } from "react";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function getSignalRms(dataArray: Uint8Array) {
  if (!dataArray.length) {
    return 0;
  }

  let sumSquares = 0;
  for (let index = 0; index < dataArray.length; index += 1) {
    const sample = (dataArray[index] - 128) / 128;
    sumSquares += sample * sample;
  }
  return Math.sqrt(sumSquares / dataArray.length);
}

export interface SignalWaveformProps {
  analyserRef: MutableRefObject<AnalyserNode | null>;
  strokeColor: string;
  fillColor: string;
  glowColor: string;
  className?: string;
}

export const SignalWaveform: React.FC<SignalWaveformProps> = ({
  analyserRef,
  strokeColor,
  fillColor,
  glowColor,
  className = "",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    let animationFrame = 0;
    let timeDomain = new Uint8Array(0);
    let barLevels = new Float32Array(0);
    let width = 0;
    let height = 0;
    let lastLevel = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      width = rect.width;
      height = rect.height;
      const devicePixelRatio = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * devicePixelRatio);
      canvas.height = Math.round(rect.height * devicePixelRatio);
      context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    resize();

    const drawIdleWave = (timestamp: number, centerY: number) => {
      context.save();
      context.globalAlpha = 0.4;
      context.strokeStyle = strokeColor;
      context.lineWidth = 1.5;
      context.beginPath();
      for (let x = 0; x <= width; x += 3) {
        const progress = x / Math.max(width, 1);
        const wave =
          Math.sin(progress * Math.PI * 4 + timestamp / 500) *
          Math.cos(progress * Math.PI * 2.5 + timestamp / 850);
        const y = centerY + wave * height * 0.07;
        if (x === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.stroke();
      context.restore();
    };

    const render = (timestamp: number) => {
      animationFrame = window.requestAnimationFrame(render);
      if (!width || !height) resize();
      context.clearRect(0, 0, width, height);

      const centerY = height / 2;
      context.save();
      context.strokeStyle = "rgba(255,255,255,0.08)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(0, centerY);
      context.lineTo(width, centerY);
      context.stroke();
      context.restore();

      const analyser = analyserRef.current;
      if (!analyser) {
        drawIdleWave(timestamp, centerY);
        return;
      }

      if (timeDomain.length !== analyser.fftSize) {
        timeDomain = new Uint8Array(analyser.fftSize);
      }
      analyser.getByteTimeDomainData(timeDomain);
      const nextLevel = clamp(getSignalRms(timeDomain) * 5.4, 0, 1);
      lastLevel += (nextLevel - lastLevel) * 0.16;

      const barCount = Math.max(20, Math.floor(width / 8));
      if (barLevels.length !== barCount) {
        barLevels = new Float32Array(barCount);
      }

      const barWidth = width / barCount;
      const samplesPerBar = timeDomain.length / barCount;
      const fillGradient = context.createLinearGradient(0, 0, width, 0);
      fillGradient.addColorStop(0, fillColor);
      fillGradient.addColorStop(0.5, strokeColor);
      fillGradient.addColorStop(1, fillColor);

      context.save();
      context.fillStyle = fillGradient;
      context.globalAlpha = 0.92;
      for (let index = 0; index < barCount; index += 1) {
        const start = Math.floor(index * samplesPerBar);
        const end = Math.max(
          start + 1,
          Math.floor((index + 1) * samplesPerBar),
        );
        let peak = 0;
        let energy = 0;
        for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
          const sample = Math.abs((timeDomain[sampleIndex] - 128) / 128);
          peak = Math.max(peak, sample);
          energy += sample;
        }
        const average = energy / Math.max(end - start, 1);
        const target = clamp(peak * 0.72 + average * 0.48, 0, 1);
        barLevels[index] += (target - barLevels[index]) * 0.3;
        const barHeight = Math.max(
          2,
          barLevels[index] * (height * 0.88 + lastLevel * height * 0.32),
        );
        const x = index * barWidth + barWidth * 0.18;
        const actualWidth = Math.max(2, barWidth * 0.62);
        context.fillRect(x, centerY - barHeight / 2, actualWidth, barHeight);
      }
      context.restore();

      const waveformAmplitude = height * (0.2 + lastLevel * 0.28);
      context.save();
      context.strokeStyle = strokeColor;
      context.lineWidth = 2;
      context.shadowBlur = 18;
      context.shadowColor = glowColor;
      context.beginPath();
      for (let x = 0; x <= width; x += 2) {
        const progress = x / Math.max(width, 1);
        const sampleIndex = Math.min(
          timeDomain.length - 1,
          Math.floor(progress * (timeDomain.length - 1)),
        );
        const sample = (timeDomain[sampleIndex] - 128) / 128;
        const y = centerY + sample * waveformAmplitude;
        if (x === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.stroke();
      context.restore();
    };

    animationFrame = window.requestAnimationFrame(render);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
    };
  }, [analyserRef, fillColor, glowColor, strokeColor]);

  return (
    <canvas
      ref={canvasRef}
      className={`block h-full w-full ${className}`.trim()}
    />
  );
};
