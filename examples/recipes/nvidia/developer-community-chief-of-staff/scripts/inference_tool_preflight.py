#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Validate structured tool calling and the configured OpenShell inference route."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

KEY_ENV = "NEMOCLAW_INFERENCE_PREFLIGHT_KEY"
TOOL_NAME = "nemoclaw_preflight"
TOOL_ARGUMENTS = {"value": "ready"}
TOOL_MARKERS = ("<|call|>", "<|tool_call|>", "<tool_call>", "</tool_call>")
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class PreflightError(Exception):
    category: str
    detail: str
    exit_code: int = 2

    def __str__(self) -> str:
        return f"Inference preflight failed ({self.category}): {self.detail}"


def completion_url(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PreflightError("configuration", "endpoint must be an http(s) URL")
    path = parsed.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path = f"{path}/chat/completions"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def display_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    hostname = parsed.hostname or "invalid-host"
    port = f":{parsed.port}" if parsed.port else ""
    return urllib.parse.urlunsplit(
        (parsed.scheme, f"{hostname}{port}", parsed.path.rstrip("/"), "", "")
    )


def _text_contains_tool_json(content: str) -> bool:
    try:
        value = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(value, dict):
        return False
    return bool({"name", "arguments", "function", "tool_calls"} & value.keys())


def validate_tool_response(response_body: bytes) -> Optional[str]:
    try:
        payload = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise PreflightError(
            "tool-protocol", "provider returned a non-JSON success response"
        ) from None

    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise PreflightError(
            "tool-protocol", "provider response did not include a completion choice"
        )
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise PreflightError(
            "tool-protocol", "provider response did not include an assistant message"
        )

    content = message.get("content")
    if isinstance(content, str) and any(marker in content for marker in TOOL_MARKERS):
        raise PreflightError(
            "tool-protocol", "provider leaked an internal tool-call marker as assistant text"
        )

    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        if isinstance(content, str) and _text_contains_tool_json(content):
            detail = "provider returned tool-call JSON as assistant text"
        else:
            detail = "provider did not return a structured tool call"
        raise PreflightError("tool-protocol", detail)
    if len(tool_calls) != 1 or not isinstance(tool_calls[0], dict):
        raise PreflightError(
            "tool-protocol", "provider returned an unexpected number of tool calls"
        )

    function = tool_calls[0].get("function")
    if not isinstance(function, dict) or function.get("name") != TOOL_NAME:
        raise PreflightError(
            "tool-protocol", "provider called a function other than the preflight tool"
        )
    arguments = function.get("arguments")
    if not isinstance(arguments, str):
        raise PreflightError(
            "tool-protocol", "provider returned non-string tool arguments"
        )
    try:
        parsed_arguments = json.loads(arguments)
    except json.JSONDecodeError:
        raise PreflightError(
            "tool-protocol", "provider returned malformed tool arguments"
        ) from None
    if parsed_arguments != TOOL_ARGUMENTS:
        raise PreflightError(
            "tool-protocol", "provider returned incorrect preflight tool arguments"
        )

    response_model = payload.get("model")
    return response_model if isinstance(response_model, str) else None


def run_tool_preflight(
    endpoint: str, model: str, key: str, timeout: float
) -> Optional[str]:
    if not key:
        raise PreflightError("configuration", "inference credential is missing")
    if not model.strip():
        raise PreflightError("configuration", "NEMOCLAW_MODEL is empty")
    if timeout <= 0:
        raise PreflightError("configuration", "timeout must be greater than zero")

    request_body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Call {TOOL_NAME} exactly once with value set to ready. "
                        "Do not answer with ordinary text."
                    ),
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": TOOL_NAME,
                        "description": "Confirm structured tool-call compatibility.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string", "enum": ["ready"]}
                            },
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
            "max_tokens": 64,
            "stream": False,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        completion_url(endpoint),
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise PreflightError(
                    "provider-response", f"unexpected HTTP status {response.status}"
                )
            return validate_tool_response(response.read(65536))
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            detail = f"provider rejected the credential (HTTP {error.code})"
            category = "authentication"
        elif error.code == 404:
            detail = "chat completions route or requested model was not found (HTTP 404)"
            category = "endpoint-or-model"
        else:
            detail = f"provider rejected the tool preflight (HTTP {error.code})"
            category = "provider-response"
        raise PreflightError(category, detail) from None
    except (TimeoutError, socket.timeout):
        raise PreflightError(
            "timeout", f"provider did not respond within {timeout:g} seconds"
        ) from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise PreflightError(
                "timeout", f"provider did not respond within {timeout:g} seconds"
            ) from None
        raise PreflightError(
            "endpoint", "provider endpoint is unreachable or its TLS certificate is invalid"
        ) from None
    except (ssl.SSLError, ConnectionError, OSError):
        raise PreflightError(
            "endpoint", "provider endpoint is unreachable or its TLS certificate is invalid"
        ) from None


def _find_route_value(route_text: str, key: str) -> str | None:
    clean = ANSI_ESCAPE.sub("", route_text)
    try:
        payload: Any = json.loads(clean)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str):
            return value
        inference = payload.get("inference")
        if isinstance(inference, dict) and isinstance(inference.get(key), str):
            return inference[key]

    match = re.search(rf"^\s*{re.escape(key)}\s*:\s*(\S+)\s*$", clean, re.I | re.M)
    return match.group(1) if match else None


def validate_active_route(route_text: str, provider: str, model: str) -> None:
    active_provider = _find_route_value(route_text, "provider")
    active_model = _find_route_value(route_text, "model")
    if not active_provider or not active_model:
        raise PreflightError(
            "active-route", "could not read provider and model from openshell inference get"
        )
    if active_provider != provider or active_model != model:
        raise PreflightError(
            "active-route",
            "active OpenShell provider/model does not match the requested configuration",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    tool = commands.add_parser("tool-call")
    tool.add_argument("--endpoint", required=True)
    tool.add_argument("--model", required=True)
    tool.add_argument("--timeout", type=float, default=10.0)
    route = commands.add_parser("active-route")
    route.add_argument("--provider", required=True)
    route.add_argument("--model", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "tool-call":
            response_model = run_tool_preflight(
                endpoint=args.endpoint,
                model=args.model,
                key=os.environ.get(KEY_ENV, ""),
                timeout=args.timeout,
            )
            model_note = f" response_model={response_model}" if response_model else ""
            print(
                "Structured tool-call preflight passed: "
                f"model={args.model}{model_note} endpoint={display_endpoint(args.endpoint)}"
            )
        else:
            validate_active_route(sys.stdin.read(), args.provider, args.model)
            print(
                "Active inference route verified: "
                f"provider={args.provider} model={args.model}"
            )
    except PreflightError as error:
        print(error, file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
