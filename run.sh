#!/usr/bin/env bash
# Helper: sources nvm, sets env vars, runs the demo. Use: ./run.sh [extra-args...]
set -euo pipefail
source "$HOME/.nvm/nvm.sh" 2>/dev/null || source "$(brew --prefix nvm 2>/dev/null)/nvm.sh"
nvm use 20 >/dev/null
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is required}"
export ANTHROPIC_API_KEY
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://model.mify.ai.srv/anthropic}"
cd "$(dirname "$0")"
exec python3 autonomous_agent_demo.py "$@"
