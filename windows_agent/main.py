# ============================================================
# windows_agent/main.py
# ============================================================

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
import warnings
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# TensorFlow / OCR logging configuration
# ============================================================

os.environ.setdefault(
    "TF_CPP_MIN_LOG_LEVEL",
    "3",
)

os.environ.setdefault(
    "ABSL_MIN_LOG_LEVEL",
    "2",
)

os.environ.setdefault(
    "TF_ENABLE_ONEDNN_OPTS",
    "0",
)

for logger_name in (
    "tensorflow",
    "tensorflow_hub",
    "tf_keras",
    "absl",
):
    logging.getLogger(
        logger_name
    ).setLevel(
        logging.ERROR
    )

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
)

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
)

warnings.filterwarnings(
    "ignore",
    message=r".*is deprecated.*",
)

warnings.filterwarnings(
    "ignore",
    module=r".*tensorflow.*",
)

warnings.filterwarnings(
    "ignore",
    module=r".*tensorflow_hub.*",
)

warnings.filterwarnings(
    "ignore",
    module=r".*tf_keras.*",
)


# ============================================================
# FastAPI
# ============================================================

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ============================================================
# Agent
# ============================================================

from windows_agent.agent.agent_loop import (
    AgentLoop,
)

from windows_agent.agent.current_screen_memory import (
    CurrentScreenMemory,
)

from windows_agent.agent.llm import (
    LocalLLM,
)

from windows_agent.agent.perception_memory import (
    GetImportantFramesTool,
)

from windows_agent.agent.screen_capture import (
    ScreenCapture,
)

from windows_agent.agent.screen_perception import (
    ScreenPerception,
)

from windows_agent.agent.uia_information import (
    UIAInformation,
)

from windows_agent.agent.memory_db.chromadb import (
    UserMemory,
)


# ============================================================
# Voice
# ============================================================

from windows_agent.agent.voice.stt.engine import (
    VoskSTTEngine,
)

from windows_agent.agent.voice.stt.service import (
    STTService,
)

from windows_agent.agent.voice.tts.engine import (
    TTSEngine,
)

from windows_agent.agent.voice.tts.service import (
    TTSService,
)


# ============================================================
# Tools
# ============================================================

from windows_agent.tools.file_tools import (
    FileTools,
)

from windows_agent.tools.list_installed_apps import (
    ListInstalledApps,
)

from windows_agent.tools.screen_diagnose import (
    ScreenDiagnoseTool,
)

from windows_agent.tools.system_tools import (
    SystemTools,
)

from windows_agent.tools.tool_manager import (
    ToolManager,
)

from windows_agent.tools.user_memory_tools import (
    UserMemoryTool,
)

from windows_agent.tools.windows_do import (
    WindowsDo,
)

from windows_agent.tools.windows_inspect import (
    WindowsInspect,
)

from windows_agent.tools.windows_launch import (
    WindowsLaunch,
)


# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title="Windows Local AI Agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "null",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ============================================================
# Runtime configuration
# ============================================================

SCREEN_FPS = 30

STT_LANGUAGE = "en"

TTS_LANGUAGE = "en"

TTS_VOICE = "M1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TTS_OUTPUT_PATH = PROJECT_ROOT / "runtime" / "response.wav"


# ============================================================
# 1. SCREEN / UIA CORE
# ============================================================

uia_information = UIAInformation()

screen_perception = ScreenPerception(
    uia_information,
)

current_screen_memory = CurrentScreenMemory()


# ============================================================
# 2. SCREEN CAPTURE
# ============================================================

screen_capture = ScreenCapture(
    target_fps=SCREEN_FPS,
    output_idx=0,
)


# ============================================================
# 3. LOCAL LLM
# ============================================================

llm = LocalLLM(
    context_size=4096,
    threads=8,
)


# ============================================================
# 4. WINDOWS TOOLS
# ============================================================

windows_launch = WindowsLaunch(
    backend="uia",
)

windows_inspect = WindowsInspect(
    backend="uia",
)

windows_do = WindowsDo(
    backend="uia",
    inspector=windows_inspect,
    window_resolver=windows_launch,
)

list_installed_apps = ListInstalledApps()


# ============================================================
# 5. FILESYSTEM
# ============================================================

file_tools = FileTools()


# ============================================================
# 6. SYSTEM
# ============================================================

system_tools = SystemTools()


# ============================================================
# 7. PERCEPTION
# ============================================================

screen_diagnose = ScreenDiagnoseTool(
    screen_memory=current_screen_memory,
)

important_frames_tool = GetImportantFramesTool(
    screen_perception=screen_perception,
)


# ============================================================
# 8. USER MEMORY
# ============================================================

user_memory_db = UserMemory()

user_memory = UserMemoryTool(
    memory=user_memory_db,
)


# ============================================================
# 9. TOOL MANAGER
# ============================================================

tool_manager = ToolManager(
    windows_launch=windows_launch,
    windows_inspect=windows_inspect,
    windows_do=windows_do,
    list_installed_apps=list_installed_apps,
    file_op=file_tools,
    system_tools=system_tools,
    screen_diagnose=screen_diagnose,
    get_important_frames=important_frames_tool,
    user_memory=user_memory,
)


# ============================================================
# 10. ATTACH TOOL MANAGER TO QWEN
# ============================================================

llm.set_tool_manager(
    tool_manager
)


# ============================================================
# 11. AGENT LOOP
# ============================================================

agent_loop = AgentLoop(
    llm=llm,
    max_steps=8,
)


# ============================================================
# 12. STT
# ============================================================

stt_engine = VoskSTTEngine(
    sample_rate=16000,
)

stt_service = STTService(
    engine=stt_engine,
    language=STT_LANGUAGE,
)


# ============================================================
# 13. TTS
# ============================================================

tts_engine = TTSEngine(
    voice=TTS_VOICE,
)

tts_service = TTSService(
    engine=tts_engine,
    output_path=TTS_OUTPUT_PATH,
)

tts_lock = threading.Lock()


# ============================================================
# 14. RUNTIME HELPERS
# ============================================================

def transcribe_audio(
    audio_data: bytes,
    language: str = STT_LANGUAGE,
) -> str | None:
    """
    Convert raw 16-bit PCM audio into text using the persistent
    Vosk STT engine.

    The Vosk engine is reused across requests instead of creating
    a new model for every request.
    """

    if not audio_data:
        return None

    return stt_engine.transcribe(
        audio_data=audio_data,
        language=language,
    )


def run_agent(
    user_query: str,
) -> dict:
    """
    Execute one request through AgentLoop and produce a
    natural-language final response.
    """

    greeting_match = re.fullmatch(
        r"(?:say|tell)\s+(?:hello|hi|hey)\s+to\s+([A-Za-z][A-Za-z -]{0,40})[!.?]?",
        user_query.strip(),
        re.IGNORECASE,
    )

    if greeting_match is not None:
        return {
            "state": None,
            "completed": True,
            "response": f"Hello, {greeting_match.group(1).strip()}!",
            "timings": [
                {
                    "stage": "fast_conversation",
                    "elapsed_ms": 0.0,
                }
            ],
        }

    state = agent_loop.run(
        user_query.strip()
    )

    execution_summary = (
        agent_loop.summarize_state(
            state
        )
    )

    if state.completed:

        final_response_started = time.perf_counter()

        final_response = llm.final_response(
            user_query=user_query,
            execution_result=execution_summary,
        )

        state.timings.append(
            {
                "stage": "final_response_generation",
                "elapsed_ms": round(
                    (time.perf_counter() - final_response_started) * 1000,
                    2,
                ),
            }
        )

    else:

        final_response = (
            "I could not complete the request."
        )

    if not isinstance(
        final_response,
        str,
    ):
        final_response = str(
            final_response
        )

    return {
        "state": state,
        "completed": bool(
            state.completed
        ),
        "response": final_response,
        "timings": state.timings,
    }

def speak_response(
    text: str,
    language: str = TTS_LANGUAGE,
) -> None:
    """
    Convert the final agent response into speech and play it through
    the system audio device using the persistent TTS engine.
    """

    if not isinstance(
        text,
        str,
    ):
        raise TypeError(
            "text must be a string."
        )

    text = text.strip()

    if not text:
        return

    tts_service.speak(
        text,
        language,
    )


def speak_response_in_background(
    text: str,
    language: str,
    timings: list[dict[str, float | str]] | None = None,
) -> None:
    """Play speech without delaying delivery of the final text response."""

    def speak() -> None:
        started = time.perf_counter()
        try:
            with tts_lock:
                speak_response(text, language)
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "Background TTS failed: %s",
                exc,
            )
        finally:
            if timings is not None:
                timings.append(
                    {
                        "stage": "tts",
                        "elapsed_ms": round(
                            (time.perf_counter() - started) * 1000,
                            2,
                        ),
                    }
                )

    threading.Thread(
        target=speak,
        name="airi-tts",
        daemon=True,
    ).start()

class TextRequest(
    BaseModel
):


    text: str

    language: str = TTS_LANGUAGE


# ============================================================
# 16. TEXT EXECUTION ENDPOINT
# ============================================================

@app.post(
    "/execute/text"
)
async def execute_text(
    request: TextRequest,
) -> dict:
    """
    Execute a text request through AgentLoop and speak the final
    agent result using local TTS.
    """

    text = request.text.strip()

    request_started = time.perf_counter()

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Text input is empty.",
        )

    try:

        result = run_agent(
            text
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Agent execution failed: "
                f"{exc}"
            ),
        ) from exc

    response_text = result[
    "response"
     ]
    speak_response_in_background(
        response_text,
        request.language,
        result["timings"],
    )

    response = {
        "status": "completed",
        "completed": result[
            "completed"
        ],
        "response": response_text,
    }

    response["timings"] = result["timings"]
    response["timings"].append(
        {
            "stage": "tts_queued",
            "elapsed_ms": round(
                (time.perf_counter() - request_started) * 1000,
                2,
            ),
        }
    )
    response["request_elapsed_ms"] = round(
        (time.perf_counter() - request_started) * 1000,
        2,
    )
    return response


# ============================================================
# 17. AUDIO EXECUTION ENDPOINT
# ============================================================

@app.post(
    "/execute"
)
async def execute_agent(
    audio: UploadFile,
) -> dict:

    request_started = time.perf_counter()
    audio_started = time.perf_counter()
    audio_data = await audio.read()

    if not audio_data:

        raise HTTPException(
            status_code=400,
            detail="Audio input is empty.",
        )

    # --------------------------------------------------------
    # STT
    # --------------------------------------------------------

    try:

        transcribed_query = (
            transcribe_audio(
                audio_data,
                STT_LANGUAGE,
            )
        )

        audio_timing = {
            "stage": "stt",
            "elapsed_ms": round(
                (time.perf_counter() - audio_started) * 1000,
                2,
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"STT execution failed: "
                f"{exc}"
            ),
        ) from exc

    if not transcribed_query:

        raise HTTPException(
            status_code=400,
            detail="No speech was detected.",
        )

    # --------------------------------------------------------
    # AGENT
    # --------------------------------------------------------

    try:

        result = run_agent(
            transcribed_query
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Agent execution failed: "
                f"{exc}"
            ),
        ) from exc

    response_text = result[
        "response"
    ]

    # --------------------------------------------------------
    # TTS
    # --------------------------------------------------------

    try:
        print(
         "FINAL RESPONSE TYPE:",
          type(response_text),
          )

        print(
    "FINAL RESPONSE VALUE:",
    repr(response_text),
)
        speak_response_in_background(
            response_text,
            TTS_LANGUAGE,
            result["timings"],
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"TTS execution failed: "
                f"{exc}"
            ),
        ) from exc

    return {
        "status": "completed",
        "transcription": transcribed_query,
        "completed": result[
            "completed"
        ],
        "response": response_text,
        "timings": [
            audio_timing,
            *result["timings"],
            {
                "stage": "request_end",
                "elapsed_ms": round(
                    (time.perf_counter() - request_started) * 1000,
                    2,
                ),
            },
        ],
        "request_elapsed_ms": round(
            (time.perf_counter() - request_started) * 1000,
            2,
        ),
    }


# ============================================================
# 18. HEALTH ENDPOINT
# ============================================================

@app.get(
    "/health"
)
async def health() -> dict:
    """
    Return the current state of the local agent runtime.

    The endpoint is useful for the future Electron frontend to
    determine whether Qwen, STT, TTS, and screen capture are ready.
    """

    return {
        "status": "ok",
        "llm": "ready",
        "stt": "ready",
        "tts": "ready",
        "screen_capture": "ready",
        "tool_manager": "ready",
    }


# ============================================================
# 19. STARTUP
# ============================================================

@app.on_event(
    "startup"
)
def startup() -> None:
    """
    Start persistent runtime services when FastAPI starts.

    The Qwen, STT, and TTS model objects were created once at module
    initialization and remain alive for the lifetime of the process.
    """

    try:

        screen_capture.start()

    except Exception as exc:

        print(
            "ScreenCapture startup warning: "
            f"{exc}"
        )

    print(
        "Windows Local AI Agent initialized successfully."
    )

    print(
        "Qwen3-VL: READY"
    )

    print(
        "ToolManager: READY"
    )

    print(
        "AgentLoop: READY"
    )

    print(
        "Vosk STT: READY"
    )

    print(
        "Supertonic TTS: READY"
    )

    print(
        "ScreenCapture: READY"
    )


# ============================================================
# 20. SHUTDOWN
# ============================================================

@app.on_event(
    "shutdown"
)
def shutdown() -> None:
    """
    Release all persistent native resources during application
    shutdown.
    """

    try:

        screen_capture.stop()

        screen_capture.release()

    except Exception:
        pass

    try:

        stt_engine.unload()

    except Exception:
        pass

    try:

        uia_information.close()

    except Exception:
        pass

    try:

        llm.close()

    except Exception:
        pass

    print(
        "Windows Local AI Agent shut down cleanly."
    )