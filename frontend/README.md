# Jerrid AI desktop frontend

Electron + React + TypeScript frontend for the local Windows agent. Electron starts or reuses `uvicorn windows_agent.main:app` on `127.0.0.1:8000`, while the renderer talks to it through typed HTTP adapters.

## Development

From this directory:

```powershell
npm install
npm run dev
```

Set `AIRI_PYTHON` to select a Python executable, or `AIRI_BACKEND_URL` to connect to an already-running local backend.

On Windows, the Electron app registers itself to start automatically when the user logs in. It starts the desktop interface and its local backend together.

The bubble is a separate 128x128 transparent Electron window. Its position is stored in Electron user data, while the main renderer and bubble synchronize status through a `BroadcastChannel`.

## Performance

The backend records `llm_first_reasoning`, `llm_verification_reasoning`, `tool_execution`, `final_response_generation`, `tts_queued`, and request timings in each response. Run the repeatable benchmark from the repository root with `python benchmarks/benchmark_agent.py --repeats 2 --timeout 30`.

Measured on 2026-08-25 after warm startup:

| Task | Result |
| --- | --- |
| Say hello to Ahmad | 18.63 ms focused request; 30.69 ms benchmark round trip |
| Open Notepad and type Ahmad | Exceeded 15 s benchmark bound |
| Open Microsoft Edge and search YouTube | Exceeded 15 s benchmark bound while the single persistent worker was busy |
| List Pictures files | Exceeded 15 s queued benchmark bound |
| Current RAM usage | Exceeded 15 s queued benchmark bound |

The 10-second target is not claimed for tool tasks on this CPU-only runtime. The largest observed bottleneck is local Qwen inference in the first reasoning step; TTS was also previously holding HTTP responses open and is now serialized in a daemon worker. Tool actions and verification remain ordered. The prompt is cached, structured/final generation is capped at 64 tokens, and llama.cpp uses a 1024-token prompt batch with 8 batch threads. These settings preserve the existing model and tool contract and should be rebenchmarked on hardware with GPU offload before further tuning.

This follows [FastAPI guidance on blocking work](https://fastapi.tiangolo.com/async/) and [Qwen3-VL deployment guidance](https://github.com/QwenLM/Qwen3-VL), which recommend treating CPU-bound inference separately from asynchronous request handling and using an optimized inference runtime where hardware supports it.

## Production build

```powershell
npm run build
npm start
```

Create a Windows package with `npm run dist`. The packaged installer uses electron-builder; signing and a branded tray icon still need to be supplied for release distribution.
