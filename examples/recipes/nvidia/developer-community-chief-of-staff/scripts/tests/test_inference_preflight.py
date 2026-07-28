# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import io
import os
import socket
import subprocess
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).parents[1] / "inference_preflight.py"
PROVIDERS_SCRIPT = SCRIPT.parent / "02-providers.sh"
SPEC = importlib.util.spec_from_file_location("inference_preflight", SCRIPT)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREFLIGHT
SPEC.loader.exec_module(PREFLIGHT)


def http_error(status: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.test/v1/chat/completions",
        code=status,
        msg="test error",
        hdrs=None,
        fp=io.BytesIO(body),
    )


class InferencePreflightTest(TestCase):
    def test_valid_configuration_uses_bounded_completion(self) -> None:
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with patch.object(PREFLIGHT.urllib.request, "urlopen", return_value=response) as open_:
            PREFLIGHT.run_preflight(
                "https://example.test/v1", "nvidia/test-model", "secret", 4
            )

        request = open_.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://example.test/v1/chat/completions"
        )
        self.assertEqual(open_.call_args.kwargs["timeout"], 4)
        self.assertNotIn("secret", request.full_url)

    def test_missing_credential_is_configuration_failure(self) -> None:
        with self.assertRaisesRegex(PREFLIGHT.PreflightError, "credential is missing") as raised:
            PREFLIGHT.run_preflight(
                "https://example.test/v1", "nvidia/test-model", "", 4
            )
        self.assertEqual(raised.exception.category, "configuration")

    def test_invalid_credential_is_authentication_failure(self) -> None:
        with patch.object(
            PREFLIGHT.urllib.request, "urlopen", side_effect=http_error(401)
        ):
            with self.assertRaises(PREFLIGHT.PreflightError) as raised:
                PREFLIGHT.run_preflight(
                    "https://example.test/v1", "nvidia/test-model", "secret", 4
                )
        self.assertEqual(raised.exception.category, "authentication")
        self.assertNotIn("secret", str(raised.exception))

    def test_unavailable_model_is_model_access_failure(self) -> None:
        body = b'{"error":{"message":"Model does not exist"}}'
        with patch.object(
            PREFLIGHT.urllib.request, "urlopen", side_effect=http_error(404, body)
        ):
            with self.assertRaises(PREFLIGHT.PreflightError) as raised:
                PREFLIGHT.run_preflight(
                    "https://example.test/v1", "nvidia/missing", "secret", 4
                )
        self.assertEqual(raised.exception.category, "model-access")

    def test_missing_completion_route_is_endpoint_failure(self) -> None:
        with patch.object(
            PREFLIGHT.urllib.request,
            "urlopen",
            side_effect=http_error(404, b"page not found"),
        ):
            with self.assertRaises(PREFLIGHT.PreflightError) as raised:
                PREFLIGHT.run_preflight(
                    "https://example.test/v1", "nvidia/test-model", "secret", 4
                )
        self.assertEqual(raised.exception.category, "endpoint")

    def test_unreachable_endpoint_is_endpoint_failure(self) -> None:
        with patch.object(
            PREFLIGHT.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError(ConnectionRefusedError()),
        ):
            with self.assertRaises(PREFLIGHT.PreflightError) as raised:
                PREFLIGHT.run_preflight(
                    "https://example.test/v1", "nvidia/test-model", "secret", 4
                )
        self.assertEqual(raised.exception.category, "endpoint")

    def test_timeout_is_distinct_from_endpoint_failure(self) -> None:
        with patch.object(
            PREFLIGHT.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError(socket.timeout()),
        ):
            with self.assertRaises(PREFLIGHT.PreflightError) as raised:
                PREFLIGHT.run_preflight(
                    "https://example.test/v1", "nvidia/test-model", "secret", 4
                )
        self.assertEqual(raised.exception.category, "timeout")

    def test_provider_outage_is_availability_failure(self) -> None:
        with patch.object(
            PREFLIGHT.urllib.request, "urlopen", side_effect=http_error(503)
        ):
            with self.assertRaises(PREFLIGHT.PreflightError) as raised:
                PREFLIGHT.run_preflight(
                    "https://example.test/v1", "nvidia/test-model", "secret", 4
                )
        self.assertEqual(raised.exception.category, "provider-availability")

    def test_display_endpoint_removes_credentials_and_query(self) -> None:
        self.assertEqual(
            PREFLIGHT.display_endpoint(
                "https://user:secret@example.test:8443/v1?api_key=secret"
            ),
            "https://example.test:8443/v1",
        )


class ProviderPhasePreflightTest(TestCase):
    def run_provider_phase(self, preflight: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_openshell = Path(temp_dir) / "openshell"
            fake_openshell.write_text(
                """#!/usr/bin/env bash
if [[ "$1 $2" == "settings get" ]]; then
  echo "providers_v2_enabled = true"
  exit 0
fi
if [[ "$1 $2" == "provider get" ]]; then
  exit 1
fi
exit 0
""",
                encoding="utf-8",
            )
            fake_openshell.chmod(0o755)
            environment = {
                **os.environ,
                "PATH": f"{temp_dir}:{os.environ['PATH']}",
                "SLACK_BOT_TOKEN": "test-bot-token",
                "SLACK_APP_TOKEN": "test-app-token",
                "NEMOCLAW_INFERENCE_PREFLIGHT": preflight,
                "ATIF_EXPORT_MODE": "local",
            }
            environment.pop("OPENAI_API_KEY", None)
            environment.pop("COMPATIBLE_API_KEY", None)
            return subprocess.run(
                ["bash", str(PROVIDERS_SCRIPT)],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_missing_credential_stops_provider_phase_by_default(self) -> None:
        result = self.run_provider_phase("1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("credential", result.stderr)
        self.assertIn("intentional offline setup", result.stderr)

    def test_explicit_bypass_allows_intentional_offline_setup(self) -> None:
        result = self.run_provider_phase("0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preflight bypassed", result.stderr)
