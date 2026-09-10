// Capture du microphone en PCM 16 kHz mono (Int16), partagée par le mode
// transcription en direct et le mode commandes vocales.

const TARGET_SAMPLE_RATE = 16000;

export function isMicSupported() {
  return (
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof window.AudioContext !== 'undefined'
  );
}

function downsample(buffer, fromRate) {
  if (fromRate === TARGET_SAMPLE_RATE) return buffer;
  const ratio = fromRate / TARGET_SAMPLE_RATE;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offset = 0;
  for (let pos = 0; pos < newLength; pos += 1) {
    const nextOffset = Math.round((pos + 1) * ratio);
    let sum = 0;
    let count = 0;
    for (let i = offset; i < nextOffset && i < buffer.length; i += 1) {
      sum += buffer[i];
      count += 1;
    }
    result[pos] = count ? sum / count : 0;
    offset = nextOffset;
  }
  return result;
}

function floatTo16BitPCM(float32Array) {
  const view = new DataView(new ArrayBuffer(float32Array.length * 2));
  float32Array.forEach((value, i) => {
    const clamped = Math.max(-1, Math.min(1, value));
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return view.buffer;
}

// Analyseur léger pour visualiser un flux MediaRecorder (mode enregistrement)
export function createStreamAnalyser(stream) {
  if (!stream) return null;
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return null;
  const context = new AudioContextClass();
  const source = context.createMediaStreamSource(stream);
  const analyser = context.createAnalyser();
  analyser.fftSize = 512;
  analyser.smoothingTimeConstant = 0.75;
  source.connect(analyser);
  return {
    analyser,
    stop: () => context.close().catch(() => {}),
  };
}

export class MicPcmStream {
    constructor(onPcm, onError) {
    this.onPcm = onPcm;
    this.onError = onError || (() => {});
    this.stream = null;
    this.context = null;
    this.processor = null;
    this.source = null;
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      this.onError(err);
      throw err;
    }
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    this.context = new AudioContextClass();
    this.source = this.context.createMediaStreamSource(this.stream);
    this.processor = this.context.createScriptProcessor(4096, 1, 1);

    // Analyseur exposé pour le visualiseur
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = 512;
    this.analyser.smoothingTimeConstant = 0.75;
    this.source.connect(this.analyser);

    this.processor.onaudioprocess = (event) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        const input = event.inputBuffer.getChannelData(0);
        const resampled = downsample(input, this.context.sampleRate);
        this.ws.send(floatTo16BitPCM(resampled));
      }
    };

    // Noeud à gain nul : pas de Larsen ni d'écho vers les haut-parleurs
    this.silentGain = this.context.createGain();
    this.silentGain.gain.value = 0;
    this.source.connect(this.processor);
    this.processor.connect(this.silentGain);
    this.silentGain.connect(this.context.destination);
  }

  attachWebSocket(ws) {
    this.ws = ws;
  }

  stop() {
    try { this.processor?.disconnect(); } catch { /* déjà déconnecté */ }
    try { this.source?.disconnect(); } catch { /* déjà déconnecté */ }
    this.context?.close().catch(() => {});
    this.stream?.getTracks().forEach((track) => track.stop());
    this.processor = null;
    this.source = null;
    this.context = null;
    this.stream = null;
    this.ws = null;
  }
}
