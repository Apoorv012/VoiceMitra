"""Generic finite-state dialogue policy engine.

This is deliberately small: a policy is just a set of named states, each of which contributes a
prompt fragment and restricts which tools the LLM is allowed to call while in that state, plus a
transition table saying which tool calls move the conversation to which next state. It is what
keeps the agent's behavior state-driven rather than "whatever the prompt says this turn" -- a
domain (e.g. domains/med_adherence) defines the concrete states; this module only knows how to
walk between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PolicyState:
    name: str
    prompt_fragment: str
    allowed_tools: list[str]
    # tool_name -> next state name. A tool call not in this map keeps the state unchanged.
    on_tool_called: dict[str, str] = field(default_factory=dict)
    is_terminal: bool = False


class PolicyEngine:
    def __init__(self, states: list[PolicyState], start_state: str) -> None:
        self._states = {s.name: s for s in states}
        if start_state not in self._states:
            raise ValueError(f"start_state '{start_state}' not in provided states")
        self.current_state_name = start_state

    @property
    def current(self) -> PolicyState:
        return self._states[self.current_state_name]

    def allowed_tools(self) -> list[str]:
        return self.current.allowed_tools

    def is_tool_allowed(self, tool_name: str) -> bool:
        return tool_name in self.current.allowed_tools

    def advance(self, tool_name: str) -> str:
        """Apply a state transition triggered by `tool_name` having been called.

        Returns the (possibly unchanged) new state name.
        """
        next_state = self.current.on_tool_called.get(tool_name)
        if next_state is not None:
            if next_state not in self._states:
                raise ValueError(f"transition from '{self.current_state_name}' on '{tool_name}' "
                                  f"points to unknown state '{next_state}'")
            self.current_state_name = next_state
        return self.current_state_name

    def is_done(self) -> bool:
        return self.current.is_terminal

    def build_system_prompt(self, base_prompt: str) -> str:
        return f"{base_prompt}\n\n{self.current.prompt_fragment}"
