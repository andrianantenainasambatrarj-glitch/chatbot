import React, { useEffect, useRef } from 'react';

// Visualiseur de niveau audio en canvas : animé en temps réel à partir d'un
// AnalyserNode, ou légèrement ondulé en attente. Respecte prefers-reduced-motion.
export default function Waveform({ analyser, active = false, height = 72, className = '' }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    let ctx;
    try {
      ctx = canvas.getContext('2d');
    } catch {
      ctx = null; // environnement sans canvas (jsdom, très vieux navigateurs)
    }
    if (!ctx) return undefined;
    const roundedRect = (x, y, w, h, r) => {
      if (typeof ctx.roundRect === 'function') {
        ctx.roundRect(x, y, w, h, r);
      } else {
        ctx.rect(x, y, w, h);
      }
    };
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false;

    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      canvas.width = w * ratio;
      canvas.height = h * ratio;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const BARS = 56;
    const freq = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;
    const start = performance.now();

    const draw = (now) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      const styles = getComputedStyle(canvas);
      const accent = styles.getPropertyValue('--accent').trim() || '#00aaff';
      const muted = styles.getPropertyValue('--text-muted').trim() || '#8b99a9';
      const slot = w / BARS;
      const barWidth = Math.max(2, slot * 0.46);

      let energy = new Array(BARS).fill(0.08);

      if (active && analyser && freq) {
        analyser.getByteFrequencyData(freq);
        for (let i = 0; i < BARS; i += 1) {
          // On échantillonne le bas du spectre (voix : 80 Hz - 4 kHz)
          const index = Math.floor(2 + (i / BARS) * 42);
          energy[i] = Math.max(0.06, freq[index] / 255);
        }
      } else if (!reduced) {
        const t = (now - start) / 700;
        for (let i = 0; i < BARS; i += 1) {
          energy[i] = 0.08 + 0.1 * (0.5 + 0.5 * Math.sin(t + i * 0.42));
        }
      }

      for (let i = 0; i < BARS; i += 1) {
        const level = energy[i];
        const barHeight = Math.max(3, level * h * 0.92);
        const x = i * slot + (slot - barWidth) / 2;
        const y = (h - barHeight) / 2;
        const isLive = active && analyser;
        ctx.fillStyle = isLive ? accent : muted;
        ctx.globalAlpha = isLive ? 0.9 : 0.5;
        ctx.beginPath();
        roundedRect(x, y, barWidth, barHeight, barWidth / 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [analyser, active]);

  return (
    <canvas
      ref={canvasRef}
      className={`waveform ${className}`}
      style={{ height }}
      aria-hidden="true"
    />
  );
}
