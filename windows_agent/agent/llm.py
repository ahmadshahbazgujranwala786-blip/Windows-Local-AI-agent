# ============================================================
# windows_agent/agent/llm.py
# ============================================================

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from llama_cpp import Llama

from windows_agent.agent.prompt import get_system_prompt
from windows_agent.tools.tool_manager import ToolManager


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = str(
    PROJECT_ROOT / "models" / "llm" / "Qwen3VL-2B-Instruct-Q4_K_M.gguf"
)


DIRECT_RESPONSE_SYSTEM_PROMPT = """
You are the conversational voice assistant for a local Windows AI agent.

Answer the user's request naturally and briefly.

Do not return JSON.
Do not mention tools.
Do not mention internal agent steps.
Do not invent actions that were not performed.
Do not claim a Windows action succeeded unless the execution result
actually confirms it.

Your response will be spoken aloud with text-to-speech, so use natural,
clear, concise language.
"""


class LocalLLM:

    def __init__(
        self,
        context_size: int = 4096,
        threads: int = 8,
    ) -> None:
        """
        Initialize the persistent local Qwen3-VL model.

        The model is loaded once and reused across all requests.
        """

        self.tool_manager: ToolManager | None = None

        self.model = Llama(
            model_path=MODEL_PATH,
            n_ctx=context_size,
            n_batch=1024,
            n_ubatch=512,
            n_threads=threads,
            n_threads_batch=threads,
            verbose=False,
        )

    def set_tool_manager(
        self,
        tool_manager: ToolManager,
    ) -> None:
        """
        Attach the central ToolManager to the local LLM.
        """

        if not isinstance(
            tool_manager,
            ToolManager,
        ):
            raise TypeError(
                "tool_manager must be a ToolManager."
            )

        self.tool_manager = tool_manager

    def generate(
        self,
        user_query: str,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        image: np.ndarray | None = None,
        stop: list[str] | None = None,
    ) -> str:
        """
        Generate one response from Qwen3-VL.

        Supports both text-only and multimodal requests.
        """

        if system_prompt is None:
            system_prompt = get_system_prompt()

        if not isinstance(
            user_query,
            str,
        ):
            raise TypeError(
                "user_query must be a string."
            )

        if not isinstance(
            system_prompt,
            str,
        ):
            raise TypeError(
                "system_prompt must be a string."
            )

        if stop is not None:

            if not isinstance(
                stop,
                list,
            ):
                raise TypeError(
                    "stop must be a list of strings or None."
                )

            for item in stop:

                if not isinstance(
                    item,
                    str,
                ):
                    raise TypeError(
                        "Every stop sequence must be a string."
                    )

        messages: list[
            dict[str, Any]
        ] = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        if image is None:

            messages.append(
                {
                    "role": "user",
                    "content": user_query,
                }
            )

        else:

            image_data = (
                self._encode_frame(
                    image
                )
            )

            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_query,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/png;base64,"
                                    f"{image_data}"
                                ),
                            },
                        },
                    ],
                }
            )

        response = (
            self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.0,
                stop=stop,
            )
        )

        content = (
            response["choices"][0]["message"]["content"]
        )

        if not isinstance(
            content,
            str,
        ):
            raise RuntimeError(
                "Qwen returned a non-string response."
            )

        return content.strip()

    def parse_output(
        self,
        model_output: str,
    ) -> dict[str, Any]:
        """
        Parse one JSON action/completion decision from Qwen.

        Valid outputs are:

            {"status":"done"}

        or:

            {
                "status":"action",
                "tool":"tool_name",
                "parameters":{}
            }
        """

        if not isinstance(
            model_output,
            str,
        ):
            raise TypeError(
                "model_output must be a string."
            )

        text = model_output.strip()

        if not text:
            raise ValueError(
                "LLM output is empty."
            )

        try:

            parsed = json.loads(
                text
            )

        except json.JSONDecodeError as exc:

            match = re.search(
                r"\{.*?\}",
                text,
                re.DOTALL,
            )

            if match is None:

                raise ValueError(
                    "LLM output does not contain "
                    "a usable JSON object."
                ) from exc

            try:

                parsed = json.loads(
                    match.group(0)
                )

            except json.JSONDecodeError as inner_exc:

                raise ValueError(
                    "Unable to parse LLM output."
                ) from inner_exc

        if not isinstance(
            parsed,
            dict,
        ):
            raise ValueError(
                "Parsed LLM output must be a JSON object."
            )

        status = str(
            parsed.get(
                "status",
                "",
            )
        ).lower()

        if status == "done":

            return {
                "status": "done",
            }

        if status != "action":

            raise ValueError(
                "Invalid LLM status."
            )

        tool = parsed.get(
            "tool"
        )

        parameters = parsed.get(
            "parameters",
            {},
        )

        if not isinstance(
            tool,
            str,
        ):
            raise ValueError(
                "LLM output is missing a valid tool."
            )

        if not isinstance(
            parameters,
            dict,
        ):
            raise ValueError(
                "LLM parameters must be an object."
            )

        return {
            "status": "action",
            "tool": tool,
            "parameters": parameters,
        }

    def execute_action(
        self,
        parsed_output: dict[str, Any],
    ) -> Any:
        """
        Execute exactly one selected tool through ToolManager.
        """

        if self.tool_manager is None:

            raise RuntimeError(
                "ToolManager has not been attached to LocalLLM."
            )

        if parsed_output.get(
            "status"
        ) != "action":

            raise ValueError(
                "execute_action() requires an action output."
            )

        tool = parsed_output.get(
            "tool"
        )

        parameters = parsed_output.get(
            "parameters",
            {},
        )

        if not isinstance(
            tool,
            str,
        ):

            raise ValueError(
                "Action is missing a valid tool."
            )

        return self.tool_manager.execute(
            tool,
            **parameters,
        )

    def process_step(
        self,
        user_query: str,
        previous_action: dict[str, Any] | None = None,
        execution_result: Any | None = None,
    ) -> dict[str, Any]:
        """
        Choose exactly one next action or declare completion.

        On the first step, Qwen is explicitly allowed to classify the
        request as either:

            conversational request → done

        or:

            desktop/task request → one action

        Follow-up steps continue using real execution results.
        """

        if not isinstance(
            user_query,
            str,
        ):
            raise TypeError(
                "user_query must be a string."
            )

        user_query = user_query.strip()

        if not user_query:
            raise ValueError(
                "user_query cannot be empty."
            )

        image: np.ndarray | None = None

        # ========================================================
        # FIRST STEP
        # ========================================================

        if previous_action is None:

            user_message = (
                "ORIGINAL USER REQUEST:\n"
                f"{user_query}\n\n"
                "FIRST-STEP ROUTING:\n"
                "First determine whether this request actually "
                "requires the Windows agent to perform an action.\n\n"
                "If the user is only asking a conversational "
                "question, requesting a greeting, asking for an "
                "explanation, or otherwise needs no Windows/tool "
                "action, return exactly:\n"
                '{"status":"done"}\n\n'
                "If the request DOES require Windows, filesystem, "
                "screen, system, or memory interaction, select "
                "exactly ONE appropriate tool action.\n\n"
                "Choose actions based on the requested end result, "
                "not on a hard-coded application workflow. For a "
                "multi-step goal, use the most general available "
                "tool and continue until the complete result is "
                "verified.\n\n"
                "Do NOT invent a tool action for ordinary "
                "conversation.\n"
                "Return exactly ONE JSON object."
            )

        # ========================================================
        # FOLLOW-UP STEP
        # ========================================================

        else:

            previous_tool = previous_action.get(
                "tool",
                "unknown",
            )

            previous_parameters = (
                previous_action.get(
                    "parameters",
                    {},
                )
            )

            user_message = (
                "ORIGINAL USER REQUEST:\n"
                f"{user_query}\n\n"
                "PREVIOUS ACTION:\n"
                f"Tool: {previous_tool}\n"
                f"Parameters: {previous_parameters}\n\n"
                "ACTUAL EXECUTION RESULT:\n"
                f"{execution_result}\n\n"
            )

            user_message += (
                "TASK COMPLETION CHECK:\n"
                "Determine whether the ORIGINAL USER REQUEST has "
                "actually been completed.\n\n"
                "A successful individual tool call does not "
                "automatically mean the task is complete.\n"
                "A found UI target does not automatically mean the "
                "task is complete.\n"
                "Verify the requested final state when necessary.\n\n"
                'If the original request is fully complete, return '
                'exactly {"status":"done"}.\n\n'
                "If the latest tool result directly confirms that "
                "the requested end result was performed, return done "
                "instead of inspecting or repeating actions.\n\n"
                "Otherwise choose exactly ONE next action.\n"
                "Choose the next action from the remaining goal and "
                "the actual result, not from assumptions about a "
                "specific application. Use sequential windows_do "
                "actions when the current focused control is enough; "
                "a type action may omit target to type into that "
                "focused control.\n"
                "Do not repeat a successful action unless it is "
                "necessary for the remaining task.\n"
            )

            # ----------------------------------------------------
            # Screen diagnosis
            # ----------------------------------------------------

            if previous_tool == "screen_diagnose":

                if not isinstance(
                    execution_result,
                    dict,
                ):
                    raise ValueError(
                        "screen_diagnose must return a dictionary."
                    )

                if execution_result.get(
                    "available"
                ) is True:

                    frame = execution_result.get(
                        "frame"
                    )

                    if not isinstance(
                        frame,
                        np.ndarray,
                    ):
                        raise ValueError(
                            "screen_diagnose returned "
                            "an invalid frame."
                        )

                    image = frame

                    user_message += (
                        "CURRENT SCREEN:\n"
                        "The current screen image is attached.\n"
                        "Use the actual screen state to decide "
                        "what remains to be done.\n\n"
                    )

                else:

                    user_message += (
                        "The screen image was unavailable.\n"
                        "Use the available execution result and "
                        "task state.\n\n"
                    )

            # ----------------------------------------------------
            # UIA target
            # ----------------------------------------------------

            elif (
                previous_tool == "find_ui_target"
                and isinstance(
                    execution_result,
                    dict,
                )
                and execution_result.get(
                    "found"
                ) is True
            ):

                target_info = (
                    execution_result.get(
                        "target",
                        {},
                    )
                )

                if isinstance(
                    target_info,
                    dict,
                ):

                    center = (
                        target_info.get(
                            "center"
                        )
                    )

                    confidence = (
                        target_info.get(
                            "confidence"
                        )
                    )

                    user_message += (
                        "UI TARGET VERIFICATION:\n"
                        "The requested UI target was successfully "
                        "located.\n"
                        f"Verified center: {center}\n"
                        f"UIA confidence: {confidence}\n"
                        "Use the verified information for the next "
                        "required action.\n"
                        "Do not invent new coordinates.\n\n"
                    )

            # ----------------------------------------------------
            # Failed UIA target
            # ----------------------------------------------------

            elif (
                previous_tool == "find_ui_target"
                and isinstance(
                    execution_result,
                    dict,
                )
                and execution_result.get(
                    "found"
                ) is not True
            ):

                user_message += (
                    "UI TARGET SEARCH FAILED.\n"
                    "Read the actual failure result.\n"
                    "Do not blindly repeat the identical search.\n"
                    "Use another suitable information or recovery "
                    "tool when appropriate.\n\n"
                )

            # ----------------------------------------------------
            # Generic failed action
            # ----------------------------------------------------

            elif (
                isinstance(
                    execution_result,
                    dict,
                )
                and execution_result.get(
                    "success"
                ) is False
            ):

                user_message += (
                    "ACTION FAILED.\n"
                    "Read the actual failure result.\n"
                    "Retry when reasonable and likely to succeed; "
                    "otherwise use a different recovery strategy.\n\n"
                )

            else:

                user_message += (
                    "Use the actual execution result to determine "
                    "what remains to be completed.\n\n"
                )

            user_message += (
                "Return exactly ONE JSON object.\n"
                "Do not return multiple actions.\n"
                "Do not return explanations.\n"
                "Do not return Markdown."
            )

        raw_output = self.generate(
            user_query=user_message,
            system_prompt=get_system_prompt(),
            image=image,
            max_tokens=64,
            stop=["\n"],
        )

        return self.parse_output(
            raw_output
        )

    def final_response(
        self,
        user_query: str,
        execution_result: Any,
    ) -> str:
        """
        Generate a natural-language final response for the user.

        This method deliberately uses a separate conversational prompt
        so the result is suitable for both the UI and TTS.
        """

        if not isinstance(
            user_query,
            str,
        ):
            raise TypeError(
                "user_query must be a string."
            )

        user_query = user_query.strip()

        if not user_query:
            raise ValueError(
                "user_query cannot be empty."
            )

        response = self.generate(
            user_query=(
                "USER REQUEST:\n"
                f"{user_query}\n\n"
                "AGENT RESULT:\n"
                f"{execution_result}\n\n"
                "Give the user a brief, natural final response.\n"
                "For a simple conversational request, answer it "
                "directly.\n"
                "For a completed Windows task, briefly confirm "
                "what was actually completed.\n"
                "Do not invent actions or results.\n"
                "Do not use JSON.\n"
                "Do not use Markdown.\n"
                "The response will be spoken aloud."
            ),
            system_prompt=(
                DIRECT_RESPONSE_SYSTEM_PROMPT
            ),
            max_tokens=64,

        )

        return response.strip()

    @staticmethod
    def _encode_frame(
        frame: np.ndarray,
        max_width: int = 1280,
        max_height: int = 720,
    ) -> str:
        """
        Resize a screen frame while preserving its aspect ratio.

        The resized frame is encoded as PNG and returned as a base64
        string for multimodal Qwen3-VL input.
        """

        if not isinstance(
            frame,
            np.ndarray,
        ):
            raise TypeError(
                "frame must be a numpy.ndarray."
            )

        if frame.size == 0:
            raise ValueError(
                "frame cannot be empty."
            )

        if frame.ndim < 2:
            raise ValueError(
                "frame must have at least two dimensions."
            )

        height, width = (
            frame.shape[:2]
        )

        scale = min(
            max_width / width,
            max_height / height,
            1.0,
        )

        if scale < 1.0:

            new_width = int(
                width * scale
            )

            new_height = int(
                height * scale
            )

            frame = cv2.resize(
                frame,
                (
                    new_width,
                    new_height,
                ),
                interpolation=cv2.INTER_AREA,
            )

        success, encoded = (
            cv2.imencode(
                ".png",
                frame,
            )
        )

        if not success:
            raise RuntimeError(
                "Failed to encode screen frame."
            )

        return base64.b64encode(
            encoded.tobytes()
        ).decode(
            "ascii"
        )

    def close(
        self,
    ) -> None:
        """
        Release the Llama model reference.

        Deleting the model releases its llama.cpp native resources when
        the LocalLLM instance is closed.
        """

        if hasattr(
            self,
            "model",
        ):
            del self.model


if __name__ == "__main__":
    pass