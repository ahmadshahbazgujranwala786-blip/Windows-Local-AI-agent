export type AgentStatus = 'idle' | 'listening' | 'thinking' | 'executing' | 'completed' | 'error';
export type Message = { id: string; role: 'user' | 'assistant'; text: string; transcription?: string; timestamp: Date; error?: boolean };
export type Health = { status: string; llm: string; stt: string; tts: string; screen_capture: string; tool_manager: string };
export type TextResult = { status: string; completed: boolean; response: string };
export type AudioResult = TextResult & { transcription: string };
export type AiriBridge = { backendUrl: () => Promise<string>; showMain: () => void; windowControl: (action: 'minimize' | 'maximize' | 'close') => void; bubbleDragStart: (point: { x: number; y: number }) => void; bubbleDragMove: (point: { x: number; y: number }) => void };

declare global { interface Window { airi: AiriBridge } }
