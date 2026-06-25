# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the in-process NeMo Relay Hermes plugin."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_plugin():
    plugin_path = Path(__file__).with_name("__init__.py")
    spec = importlib.util.spec_from_file_location(
        "nemo_relay_plugin_under_test", plugin_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_forward_sanitizes_openshell_env_placeholders(monkeypatch):
    plugin = _load_plugin()

    class FakeClient:
        def __init__(self):
            self.calls = []

        def post(self, url, json):
            self.calls.append((url, json))

    fake_client = FakeClient()
    monkeypatch.setattr(plugin, "_GATEWAY_LOOKED_UP", True)
    monkeypatch.setattr(plugin, "_GATEWAY_URL", "http://relay.local")
    monkeypatch.setattr(plugin, "_CLIENT", fake_client)

    payload = {
        "hook_event_name": "pre_api_request",
        "request": {
            "body": {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "keep this text but hide "
                            "openshell:resolve:env:FAKE_TOKEN"
                        ),
                    }
                ]
            }
        },
        "metadata": ("openshell:resolve:env:ANOTHER_TOKEN",),
    }

    plugin._forward(payload)

    assert fake_client.calls == [
        (
            "http://relay.local/hooks/hermes",
            {
                "hook_event_name": "pre_api_request",
                "request": {
                    "body": {
                        "messages": [
                            {
                                "role": "user",
                                "content": (
                                    "keep this text but hide "
                                    "[openshell env placeholder]"
                                ),
                            }
                        ]
                    }
                },
                "metadata": ["[openshell env placeholder]"],
            },
        )
    ]
    assert "openshell:resolve:env:" not in json.dumps(fake_client.calls[0][1])
