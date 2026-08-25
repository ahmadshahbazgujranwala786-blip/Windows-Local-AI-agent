from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from windows_agent.agent.llm import LocalLLM


DEFAULT_MAX_STEPS = 10


@dataclass
class AgentState:
    """
    Store the state of one agent task.

    The state keeps the original user request, the current step,
    selected actions, execution results, and completion status.
    """

    user_query: str

    step: int = 0

    completed: bool = False

    last_action: dict[str, Any] | None = None

    last_result: Any | None = None

    actions: list[dict[str, Any]] = field(
        default_factory=list
    )

    results: list[Any] = field(
        default_factory=list
    )


class AgentLoop:
    """
    Run the main Qwen → tool → result reasoning loop.

    Qwen selects one action at a time. The selected action is
    executed through LocalLLM and the real result is sent back
    to Qwen for the next decision.
    """

    def __init__(
        self,
        llm: LocalLLM,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        """
        Initialize the agent loop.

        The LocalLLM instance must already have its ToolManager
        attached before the loop is started.
        """

        if not isinstance(
            llm,
            LocalLLM,
        ):
            raise TypeError(
                "llm must be a LocalLLM."
            )

        if max_steps <= 0:
            raise ValueError(
                "max_steps must be greater than zero."
            )

        self._llm = llm
        self._max_steps = max_steps

    def run(
        self,
        user_query: str,
    ) -> AgentState:
        """
        Execute one complete user task.

        The loop continues until Qwen returns a done response
        or the maximum number of reasoning steps is reached.
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

        state = AgentState(
            user_query=user_query
        )

        previous_action: dict[str, Any] | None = None

        execution_result: Any | None = None

        while state.step < self._max_steps:

            state.step += 1

            print()
            print("=" * 60)
            print(
                f"AGENT STEP {state.step}"
            )
            print("=" * 60)

            # ------------------------------------------------
            # Ask Qwen for the next decision.
            # ------------------------------------------------

            decision = self._llm.process_step(
                user_query=state.user_query,
                previous_action=previous_action,
                execution_result=execution_result,
            )

            print()
            print("QWEN DECISION:")
            print(decision)

            # ------------------------------------------------
            # Check whether Qwen completed the task.
            # ------------------------------------------------

            if decision.get(
                "status"
            ) == "done":

                state.completed = True

                print()
                print(
                    "Qwen reported that the task is complete."
                )

                break

            # ------------------------------------------------
            # Validate action response.
            # ------------------------------------------------

            if decision.get(
                "status"
            ) != "action":

                raise RuntimeError(
                    "Qwen returned an invalid decision."
                )

            tool = decision.get(
                "tool"
            )

            parameters = decision.get(
                "parameters",
                {},
            )

            if not isinstance(
                tool,
                str,
            ):
                raise RuntimeError(
                    "Qwen action does not contain "
                    "a valid tool name."
                )

            if not isinstance(
                parameters,
                dict,
            ):
                raise RuntimeError(
                    "Qwen action parameters must "
                    "be a dictionary."
                )

            # ------------------------------------------------
            # Record selected action.
            # ------------------------------------------------

            action_record = {
                "step": state.step,
                "tool": tool,
                "parameters": parameters,
            }

            state.actions.append(
                action_record
            )

            state.last_action = decision

            print()
            print("SELECTED TOOL:")
            print(tool)

            print(
                "PARAMETERS:"
            )
            print(parameters)

            # ------------------------------------------------
            # Execute actual tool.
            # ------------------------------------------------

            print()
            print(
                "EXECUTING ACTION..."
            )

            execution_result = (
                self._llm.execute_action(
                    decision
                )
            )

            state.results.append(
                execution_result
            )

            state.last_result = (
                execution_result
            )

            print()
            print(
                "EXECUTION RESULT:"
            )
            print(execution_result)

            # ------------------------------------------------
            # Preserve the action/result for the next
            # Qwen reasoning step.
            # ------------------------------------------------

            previous_action = decision

        # ----------------------------------------------------
        # Maximum-step protection.
        # ----------------------------------------------------

        if not state.completed:

            raise RuntimeError(
                "Agent reached the maximum number "
                f"of steps ({self._max_steps}) "
                "without completing the task."
            )

        print()
        print("=" * 60)
        print(
            "AGENT TASK COMPLETE"
        )
        print("=" * 60)

        return state

    @staticmethod
    def summarize_state(
        state: AgentState,
    ) -> dict[str, Any]:
        """
        Convert AgentState into a normal dictionary.

        Useful for debugging, testing, logging, and future
        persistence of the agent's execution history.
        """

        if not isinstance(
            state,
            AgentState,
        ):
            raise TypeError(
                "state must be an AgentState."
            )

        return {
            "user_query": state.user_query,
            "step": state.step,
            "completed": state.completed,
            "actions": state.actions,
            "results": state.results,
            "last_action": state.last_action,
            "last_result": state.last_result,
        }