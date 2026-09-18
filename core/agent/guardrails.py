"""Generic safety-guardrail check pipeline.

Distinct from policy.py: the policy engine controls conversation *flow* (what state comes next).
Guardrails are safety constraints checked *regardless* of flow/state -- independent of what the
LLM was prompted to do or decided to do this turn. Three kinds of checks, all domain-supplied:

- text checks: run on the LLM's outgoing text before it's spoken/sent, can block or rewrite it
  (e.g. "never recommend a dosage change").
- tool-call checks: run on a tool call's validated arguments before it's dispatched, can veto it
  (e.g. a symptom logged as 'severe' but the call is about to end without escalating).
- forced-action checks: run every turn *independent* of what the LLM chose to do, and can inject a
  tool call that overrides the LLM entirely (e.g. a red-flag symptom was mentioned this
  conversation -> force `escalate_to_doctor`, whether or not the LLM tried to move on).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class GuardrailViolation(Exception):
    """Raised by a text or tool-call check to block the offending output/call."""


@dataclass
class ForcedAction:
    tool_name: str
    args: dict
    reason: str


TextCheck = Callable[[str, Any], str]
ToolCallCheck = Callable[[str, dict, Any], None]
ForcedActionCheck = Callable[[Any], ForcedAction | None]


class GuardrailPipeline:
    def __init__(self) -> None:
        self._text_checks: list[TextCheck] = []
        self._tool_call_checks: list[ToolCallCheck] = []
        self._forced_action_checks: list[ForcedActionCheck] = []

    def add_text_check(self, check: TextCheck) -> None:
        self._text_checks.append(check)

    def add_tool_call_check(self, check: ToolCallCheck) -> None:
        self._tool_call_checks.append(check)

    def add_forced_action_check(self, check: ForcedActionCheck) -> None:
        self._forced_action_checks.append(check)

    def check_text(self, text: str, context: Any) -> str:
        """Run all text checks in order; each may rewrite the text. Raises GuardrailViolation
        if a check decides the text must be blocked outright."""
        for check in self._text_checks:
            text = check(text, context)
        return text

    def check_tool_call(self, tool_name: str, args: dict, context: Any) -> None:
        for check in self._tool_call_checks:
            check(tool_name, args, context)

    def forced_action(self, context: Any) -> ForcedAction | None:
        for check in self._forced_action_checks:
            action = check(context)
            if action is not None:
                return action
        return None
