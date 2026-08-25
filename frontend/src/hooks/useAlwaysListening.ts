import { useEffect, useRef, useState } from 'react';

function pcmBlob(chunks: Float32Array[], rate: number) {
  const ratio = rate / 16000;
  const source = Float32Array.from(chunks.flatMap((chunk) => [...chunk]));
  const samples = ratio === 1 ? source : Float32Array.from({ length: Math.round(source.length / ratio) }, (_, index) => source[Math.min(Math.floor(index * ratio), source.length - 1)]);
  const bytes = new ArrayBuffer(samples.length * 2);
  const view = new DataView(bytes);
  samples.forEach((sample, index) => view.setInt16(index * 2, Math.max(-1, Math.min(1, sample)) * 0x7fff, true));
  return new Blob([bytes], { type: 'application/octet-stream' });
}

export function useAlwaysListening(enabled: boolean, onSpeech: (audio: Blob) => void) {
  const callback = useRef(onSpeech);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  callback.current = onSpeech;

  useEffect(() => {
    if (!enabled) { setActive(false); setError(null); return; }
    let disposed = false;
    let context: AudioContext | null = null;
    let stream: MediaStream | null = null;
    let processor: ScriptProcessorNode | null = null;
    let source: MediaStreamAudioSourceNode | null = null;
    let chunks: Float32Array[] = [];
    let speaking = false;
    let silenceFrames = 0;
    let speechFrames = 0;

    const stop = () => {
      processor?.disconnect(); source?.disconnect(); stream?.getTracks().forEach((track) => track.stop());
      if (context && context.state !== 'closed') void context.close();
    };
    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
        if (disposed) { stream.getTracks().forEach((track) => track.stop()); return; }
        context = new AudioContext(); source = context.createMediaStreamSource(stream); processor = context.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = (event) => {
          const frame = new Float32Array(event.inputBuffer.getChannelData(0));
          const rms = Math.sqrt(frame.reduce((sum, sample) => sum + sample * sample, 0) / frame.length);
          const speech = rms > 0.018;
          if (speech) { if (!speaking) { speaking = true; chunks = []; speechFrames = 0; } chunks.push(frame); speechFrames += 1; silenceFrames = 0; }
          else if (speaking) { chunks.push(frame); silenceFrames += 1; if (silenceFrames >= 5 && speechFrames >= 3) { const utterance = pcmBlob(chunks, context?.sampleRate ?? 16000); speaking = false; chunks = []; silenceFrames = 0; speechFrames = 0; callback.current(utterance); } }
        };
        source.connect(processor); processor.connect(context.destination); setActive(true);
      } catch { setError('Microphone access is unavailable. Enable it in Windows privacy settings.'); setActive(false); }
    };
    void start();
    return () => { disposed = true; stop(); setActive(false); };
  }, [enabled]);

  return { active, error };
}
