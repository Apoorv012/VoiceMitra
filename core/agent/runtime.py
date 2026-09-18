"""Generic agent runtime: wires a Transport + LLM + ToolRegistry + PolicyEngine +
GuardrailPipeline into a running conversation.

`run_chat_session` here is a manual turn loop against any OpenAI-compatible chat-completions
client, used with ChatTransport to build and debug domains/med_adherence's actual logic before
audio is involved (Chunk 2). Chunk 3 adds a Pipecat-pipeline-based voice entrypoint that reuses
this exact same ToolRegistry / PolicyEngine / GuardrailPipeline / domain code -- only the turn-loop
mechanics differ, because a real-time audio pipeline is unavoidably orchestrated differently from a
synchronous text REPL (that's what makes it a different Transport in the first place, not a defect
in this one).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from core.agent.guardrails import GuardrailPipeline, GuardrailViolation
from core.agent.policy import PolicyEngine
from core.agent.tool_registry import ToolCallError, ToolRegistry
from core.transport.base import Transport


@dataclass
class AgentConfig:
    llm_client: AsyncOpenAI
    model: str
    base_system_prompt: str
    tool_registry: ToolRegistry
    policy: PolicyEngine
    guardrails: GuardrailPipeline


async def run_chat_session(transport: Transport, config: AgentConfig, context: Any) -> None:
    # A system-prompt-only request (no user/model turns yet) is how the very first LLM call looks,
    # since the agent speaks first (it's calling the patient, not the other way round). OpenAI and
    # Sarvam both accept that; Gemini's OpenAI-compat endpoint rejects it ("contents is not
    # specified"). This neutral seed message keeps every provider working without branching on
    # which one is in use.
    messages: list[dict] = [{"role": "user", "content": "(the call has just connected)"}]
    await transport.start()

    while True:
        forced = config.guardrails.forced_action(context)
        if forced is not None:
            result = await _run_tool(forced.tool_name, forced.args, config, context, note=forced.reason)
            messages.append({
                "role": "system",
                "content": (
                    f"[guardrail override -- {forced.reason}] Called {forced.tool_name}; "
                    f"result: {json.dumps(result)}. Continue the conversation accordingly."
                ),
            })
            # Fall through to the LLM turn below even in a terminal state, so it can deliver a
            # closing line; the loop ends via the `policy.is_done()` check after that line sends.

        system_prompt = config.policy.build_system_prompt(config.base_system_prompt)
        allowed = set(config.policy.allowed_tools())
        full_schema = config.tool_registry.openai_tools_schema()
        allowed_schema = [t for t in full_schema if t["function"]["name"] in allowed]

        # Once the conversation has any prior tool call/result in it, some OpenAI-compatible
        # backends (Sarvam included) require `tools` to stay non-empty on every later request --
        # and separately, tool_choice="none" was observed to make Sarvam's model return totally
        # empty output (no text either), so it's never used. Instead: always offer the full
        # schema with tool_choice="auto" once any tool history exists, and enforce which tools
        # are actually *usable* this turn via the allowed-tools check in _run_tool below, not via
        # what's offered to the model.
        has_tool_history = any(m.get("role") == "tool" for m in messages)
        if allowed_schema or has_tool_history:
            tools_param = allowed_schema or full_schema
            tool_choice = "auto"
        else:
            tools_param, tool_choice = None, None

        response = await config.llm_client.chat.completions.create(
            model=config.model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            **({"tools": tools_param, "tool_choice": tool_choice} if tools_param else {}),
        )
        choice = response.choices[0].message

        if choice.tool_calls:
            messages.append({
                "role": "assistant",
                "content": choice.content,
                "tool_calls": [tc.model_dump() for tc in choice.tool_calls],
            })
            for tc in choice.tool_calls:
                if tc.function.name not in allowed:
                    result = {"error": f"'{tc.function.name}' is not usable at this point in the call"}
                    context.record_tool_call(tc.function.name, {}, result, note="blocked: not allowed in current state")
                else:
                    args = json.loads(tc.function.arguments or "{}")
                    result = await _run_tool(tc.function.name, args, config, context)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
            continue  # let the LLM speak once it has seen the tool result(s) -- even in a
            # terminal state, so it gets to deliver a closing line; the loop ends via the
            # `policy.is_done()` check below, after that line has been sent.

        text = choice.content or ""
        try:
            text = config.guardrails.check_text(text, context)
        except GuardrailViolation as e:
            text = f"Sorry, I can't help with that. {e}"
        messages.append({"role": "assistant", "content": text})
        context.record_agent_text(text)
        await transport.send_text(text)

        if config.policy.is_done():
            break

        user_text = await transport.receive_text()
        if user_text is None:
            break
        context.record_user_text(user_text)
        context.observe_user_text(user_text)
        messages.append({"role": "user", "content": user_text})

    await transport.end()


async def _run_tool(
    name: str, args: dict, config: AgentConfig, context: Any, *, note: str | None = None
) -> Any:
    try:
        config.guardrails.check_tool_call(name, args, context)
        result = await config.tool_registry.dispatch(name, args, context=context)
    except (GuardrailViolation, ToolCallError) as e:
        result = {"error": str(e)}
    finally:
        config.policy.advance(name)
    result = result if result is not None else {"ok": True}
    context.record_tool_call(name, args, result, note=note)
    return result
