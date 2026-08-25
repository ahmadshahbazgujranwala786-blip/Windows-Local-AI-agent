import type { AudioResult, Health, TextResult } from '../types';

const fallback = 'http://127.0.0.1:8000';
async function baseUrl() { return window.airi?.backendUrl?.() ?? fallback; }
async function parse<T>(response: Response): Promise<T> { if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(typeof body.detail === 'string' ? body.detail : 'The local agent could not complete that request.'); } return response.json() as Promise<T>; }
export async function health() { return parse<Health>(await fetch(`${await baseUrl()}/health`)); }
export async function executeText(text: string) { return parse<TextResult>(await fetch(`${await baseUrl()}/execute/text`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language: 'en' }) })); }
export async function executeAudio(audio: Blob) { const form = new FormData(); form.append('audio', audio, 'speech.pcm'); return parse<AudioResult>(await fetch(`${await baseUrl()}/execute`, { method: 'POST', body: form })); }
