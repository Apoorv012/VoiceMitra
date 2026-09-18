"""Base for domain-specific per-conversation state, passed opaquely through core/agent/ (tools,
policy, guardrails all just receive `context: Any` and never touch its fields).

The exceptions are these hook methods, which the runtime calls at defined points so a domain can
react (react to red-flag phrasing, record a transcript, whatever) without core/agent/ needing to
know anything about conversation transcripts, persistence, or domain state shape:

- observe_user_text: once per turn, right after receiving the other party's raw text, before
  invoking the LLM (e.g. red-flag symptom keyword scanning that feeds a forced-action guardrail).
- record_user_text / record_agent_text: once per turn, for whichever side just spoke.
- record_tool_call: once per tool dispatch (LLM-issued or guardrail-forced), with its args and
  result.
"""

from __future__ import annotations

from typing import Any


class AgentContext:
    def observe_user_text(self, text: str) -> None:
        pass

    def record_user_text(self, text: str) -> None:
        pass

    def record_agent_text(self, text: str) -> None:
        pass

    def record_tool_call(self, name: str, args: dict, result: Any, *, note: str | None = None) -> None:
        pass
