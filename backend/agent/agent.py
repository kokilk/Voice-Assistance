"""
K's agentic loop — drives a multi-turn Claude conversation
with tool use until a final text reply is produced.
"""
from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from backend.agent.prompts import build_system_prompt
from backend.agent.tools import TOOL_DEFINITIONS, call_tool

MAX_TOOL_ROUNDS = 8
MODEL = "claude-sonnet-4-6"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def run(transcript: str) -> tuple[str, str | None]:
    """
    Run the agentic loop for a single voice command.

    Args:
        transcript: The user's spoken text.

    Returns:
        (reply, action_taken) — reply is K's spoken response,
        action_taken is a brief label of what K did (or None).
    """
    client = _get_client()
    system = build_system_prompt()
    messages: list[dict[str, Any]] = [{"role": "user", "content": transcript}]

    action_taken: str | None = None
    tools_called: list[str] = []

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Collect all content blocks
        assistant_content: list[dict[str, Any]] = []
        tool_use_blocks: list[Any] = []
        text_blocks: list[str] = []

        for block in response.content:
            if block.type == "text":
                text_blocks.append(block.text)
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                tool_use_blocks.append(block)
                assistant_content.append({
                    "type":  "tool_use",
                    "id":    block.id,
                    "name":  block.name,
                    "input": block.input,
                })

        # Add assistant turn to history
        messages.append({"role": "assistant", "content": assistant_content})

        # If no tool calls — we have the final reply
        if response.stop_reason == "end_turn" or not tool_use_blocks:
            reply = " ".join(text_blocks).strip() or "Done."
            action_taken = ", ".join(tools_called) if tools_called else None
            return reply, action_taken

        # Execute all tool calls and collect results
        tool_results: list[dict[str, Any]] = []
        for block in tool_use_blocks:
            tools_called.append(block.name)
            result = call_tool(block.name, block.input)
            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     json.dumps(result, default=str),
            })

        # Add tool results as user turn
        messages.append({"role": "user", "content": tool_results})

    # Fallback if we hit MAX_TOOL_ROUNDS
    return "I ran into trouble completing that. Please try again.", ", ".join(tools_called) or None
