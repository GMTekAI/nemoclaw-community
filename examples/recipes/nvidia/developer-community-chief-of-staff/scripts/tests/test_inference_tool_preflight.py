# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional
from unittest import TestCase
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).parents[1] / "inference_tool_preflight.py"
SPEC = importlib.util.spec_from_file_location("inference_tool_preflight", SCRIPT)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREFLIGHT
SPEC.loader.exec_module(PREFLIGHT)


def response_body(
    *,
    name: str = "nemoclaw_preflight",
    arguments: str = '{"value":"ready"}',
    content: Optional[str] = None,
) -> bytes:
    return json.dumps(
        {
            "model": "provider/model",
            "choices": [
                {
                    "message": {
                        "content": content,
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {"name": name, "arguments": arguments},
                            }
                        ],
                    }
                }
            ],
        }
    ).encode()


class ToolCallResponseTest(TestCase):
    def test_accepts_expected_structured_tool_call(self) -> None:
        self.assertEqual(
            PREFLIGHT.validate_tool_response(response_body()), "provider/model"
        )

    def test_rejects_missing_structured_tool_call(self) -> None:
        body = b'{"choices":[{"message":{"content":"ready"}}]}'
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "structured tool call"):
            PREFLIGHT.validate_tool_response(body)

    def test_rejects_tool_json_returned_as_text(self) -> None:
        body = b'{"choices":[{"message":{"content":"{\\"name\\":\\"nemoclaw_preflight\\"}"}}]}'
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "JSON as assistant text"):
            PREFLIGHT.validate_tool_response(body)

    def test_rejects_internal_tool_marker(self) -> None:
        body = b'{"choices":[{"message":{"content":"}<|call|>"}}]}'
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "internal tool-call marker"):
            PREFLIGHT.validate_tool_response(body)

    def test_rejects_wrong_function(self) -> None:
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "other than"):
            PREFLIGHT.validate_tool_response(response_body(name="github-readonly-live"))

    def test_rejects_malformed_arguments(self) -> None:
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "malformed"):
            PREFLIGHT.validate_tool_response(response_body(arguments="{"))

    def test_rejects_incorrect_arguments(self) -> None:
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "incorrect"):
            PREFLIGHT.validate_tool_response(
                response_body(arguments='{"value":"not-ready"}')
            )


class ToolCallRequestTest(TestCase):
    def test_sends_forced_bounded_tool_request_without_key_in_url(self) -> None:
        response = MagicMock()
        response.status = 200
        response.read.return_value = response_body()
        response.__enter__.return_value = response
        with patch.object(
            PREFLIGHT.urllib.request, "urlopen", return_value=response
        ) as open_:
            PREFLIGHT.run_tool_preflight(
                "https://example.test/v1", "nvidia/test-model", "secret", 4
            )

        request = open_.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(
            request.full_url, "https://example.test/v1/chat/completions"
        )
        self.assertEqual(open_.call_args.kwargs["timeout"], 4)
        self.assertEqual(
            payload["tool_choice"]["function"]["name"], "nemoclaw_preflight"
        )
        self.assertEqual(payload["tools"][0]["type"], "function")
        self.assertNotIn("secret", request.full_url)

    def test_missing_key_is_sanitized(self) -> None:
        with self.assertRaises(PREFLIGHT.PreflightError) as raised:
            PREFLIGHT.run_tool_preflight(
                "https://example.test/v1", "nvidia/test-model", "", 4
            )
        self.assertEqual(raised.exception.category, "configuration")

    def test_display_endpoint_removes_credentials_and_query(self) -> None:
        self.assertEqual(
            PREFLIGHT.display_endpoint(
                "https://user:secret@example.test:8443/v1?api_key=secret"
            ),
            "https://example.test:8443/v1",
        )


class ActiveRouteTest(TestCase):
    def test_accepts_expected_text_route(self) -> None:
        PREFLIGHT.validate_active_route(
            "Provider: compatible-endpoint\nModel: nvidia/test-model\n",
            "compatible-endpoint",
            "nvidia/test-model",
        )

    def test_accepts_expected_json_route(self) -> None:
        PREFLIGHT.validate_active_route(
            '{"provider":"compatible-endpoint","model":"nvidia/test-model"}',
            "compatible-endpoint",
            "nvidia/test-model",
        )

    def test_rejects_model_mismatch_without_echoing_active_model(self) -> None:
        with self.assertRaises(PREFLIGHT.PreflightError) as raised:
            PREFLIGHT.validate_active_route(
                "Provider: compatible-endpoint\nModel: other/model\n",
                "compatible-endpoint",
                "nvidia/test-model",
            )
        self.assertEqual(raised.exception.category, "active-route")
        self.assertNotIn("other/model", str(raised.exception))

    def test_rejects_unreadable_route(self) -> None:
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "could not read"):
            PREFLIGHT.validate_active_route(
                "No inference configured", "compatible-endpoint", "nvidia/test-model"
            )
