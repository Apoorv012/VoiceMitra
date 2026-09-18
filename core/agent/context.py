"""Base for domain-specific per-conversation state, passed opaquely through core/agent/ (tools,
policy, guardrails all just receive `context: Any` and never touch its fields).

The one exception is `observe_user_text`: the runtime calls it once per turn, right after
receiving the other party's raw text and before invoking the LLM, so a domain can react to what
was actually said (e.g. red-flag symptom keyword scanning that feeds a forced-action guardrail)
without core/agent/ needing to know anything about conversation transcripts or domain state shape.
"""

from __future__ import annotations


class AgentContext:
    def observe_user_text(self, text: str) -> None:
        pass
