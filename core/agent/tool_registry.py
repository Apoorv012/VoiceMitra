"""Decorator-based registration of LLM-callable tools, with pydantic argument validation.

A domain (e.g. domains/med_adherence) registers its tools against a ToolRegistry instance. The
registry knows how to describe itself in OpenAI/Sarvam function-calling `tools` schema, and how to
validate+dispatch an incoming tool call by name.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ValidationError


@dataclass
class RegisteredTool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., Awaitable[Any]]

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


class ToolCallError(Exception):
    """Raised when a tool call fails argument validation or execution."""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, *, name: str, description: str, args_model: type[BaseModel]):
        def decorator(handler: Callable[..., Awaitable[Any]]):
            if not inspect.iscoroutinefunction(handler):
                raise TypeError(f"tool handler for '{name}' must be an async function")
            self._tools[name] = RegisteredTool(
                name=name, description=description, args_model=args_model, handler=handler
            )
            return handler

        return decorator

    def openai_tools_schema(self) -> list[dict]:
        return [t.openai_schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    async def dispatch(self, name: str, raw_arguments: dict, *, context: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolCallError(f"unknown tool '{name}'")
        try:
            args = tool.args_model(**raw_arguments)
        except ValidationError as e:
            raise ToolCallError(f"invalid arguments for '{name}': {e}") from e
        return await tool.handler(args, context)
