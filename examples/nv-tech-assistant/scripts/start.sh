#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Start or recover the nv-tech-assistant sandbox. The NemoClaw start command
# is safe to run when the sandbox is already running.

set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$DIR/_lib.sh"

command -v nemoclaw >/dev/null || { echo "nemoclaw not in PATH — run scripts/onboard.sh first" >&2; exit 1; }

if ! sandbox_exists "$NEMOCLAW_SANDBOX_NAME"; then
  echo "Sandbox '$NEMOCLAW_SANDBOX_NAME' not found — run scripts/onboard.sh first" >&2
  exit 1
fi

run nemoclaw "$NEMOCLAW_SANDBOX_NAME" start

echo
echo "Sandbox is ready."
echo "  Interactive shell: nemoclaw $NEMOCLAW_SANDBOX_NAME connect"
echo "  One agent turn:    nemoclaw $NEMOCLAW_SANDBOX_NAME agent --agent main -m '<question>'"
