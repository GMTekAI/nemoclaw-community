# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


RECIPE_DIR = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cache_helper():
    return load_module(
        "outlook_cache",
        RECIPE_DIR / "scripts/lib/outlook_cache.py",
    )


def load_login_helper():
    return load_module(
        "login_ms_graph",
        RECIPE_DIR / "scripts/login-ms-graph.py",
    )


def test_explicit_refresh_expiry_wins(tmp_path):
    helper = load_cache_helper()
    cache = tmp_path / "token.json"
    cache.write_text(
        json.dumps(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at_ms": 1_000,
                "refresh_expires_at_ms": 9_000,
            }
        ),
        encoding="utf-8",
    )

    assert helper.refresh_expires_at_ms(cache) == 9_000


def test_expired_refresh_horizon_is_not_replaced_by_legacy_default(tmp_path):
    helper = load_cache_helper()
    cache = tmp_path / "token.json"
    cache.write_text(
        json.dumps(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at_ms": 1_000,
                "refresh_expires_at_ms": 1,
            }
        ),
        encoding="utf-8",
    )

    assert helper.refresh_expires_at_ms(cache) == 1


def test_legacy_cache_uses_mtime_not_access_expiry(tmp_path):
    helper = load_cache_helper()
    cache = tmp_path / "token.json"
    cache.write_text(
        json.dumps(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at_ms": 1_000,
            }
        ),
        encoding="utf-8",
    )

    expected = int(cache.stat().st_mtime * 1000) + helper.DEFAULT_REFRESH_LIFETIME_MS
    assert helper.refresh_expires_at_ms(cache) == expected


def test_missing_refresh_token_is_stale(tmp_path):
    helper = load_cache_helper()
    cache = tmp_path / "token.json"
    cache.write_text(
        json.dumps({"access_token": "access", "expires_at_ms": 1_000}),
        encoding="utf-8",
    )

    assert helper.refresh_expires_at_ms(cache) == 0


def test_malformed_or_non_object_cache_is_stale(tmp_path):
    helper = load_cache_helper()
    malformed = tmp_path / "malformed.json"
    malformed.write_text("not-json", encoding="utf-8")
    non_object = tmp_path / "list.json"
    non_object.write_text("[]", encoding="utf-8")

    assert helper.refresh_expires_at_ms(malformed) == 0
    assert helper.refresh_expires_at_ms(non_object) == 0


def test_refresh_lifetime_uses_response_or_conservative_default():
    login = load_login_helper()

    assert login.refresh_token_lifetime_seconds(
        {"refresh_token_expires_in": 86_400}
    ) == 86_400
    assert login.refresh_token_lifetime_seconds({}) == (
        login.DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS
    )
    assert login.refresh_token_lifetime_seconds(
        {"refresh_token_expires_in": "invalid"}
    ) == login.DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS
