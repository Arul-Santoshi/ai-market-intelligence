#!/usr/bin/env bash
# ------------------------------------------------------------------
# AI Market Intelligence — cross-platform start script (Linux / macOS)
#
# Usage:
#   ./start.sh              # Launch both the scheduler and the dashboard
#   ./start.sh --dashboard  # Launch only the Streamlit dashboard
#   ./start.sh --scheduler  # Launch only the background scheduler
#   ./start.sh --test       # Run the pipeline once (no scheduler, no dashboard)
# ------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colours ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Colour

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Virtual-environment detection ───────────────────────────────────
activate_venv() {
    if [[ -d "venv" ]]; then
        # shellcheck disable=SC1091
        source venv/bin/activate
        ok "Activated virtual environment (venv)"
    elif [[ -d ".venv" ]]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        ok "Activated virtual environment (.venv)"
    elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
        ok "Already in virtual environment ($VIRTUAL_ENV)"
    else
        warn "No virtual environment found — using system Python"
    fi
}

# ── Dependency check ────────────────────────────────────────────────
check_deps() {
    if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
        fail "Python not found. Install Python 3.10+ first."
    fi

    PYTHON="$(command -v python3 || command -v python)"
    info "Using Python: $PYTHON ($($PYTHON --version 2>&1))"

    if ! "$PYTHON" -c "import streamlit" &>/dev/null; then
        warn "Missing dependencies — installing from requirements.txt ..."
        "$PYTHON" -m pip install -r requirements.txt
    fi
}

# ── .env check ──────────────────────────────────────────────────────
check_env() {
    if [[ ! -f ".env" ]]; then
        warn ".env file not found — copy .env.example and fill in your API keys"
    fi
}

# ── Start modes ─────────────────────────────────────────────────────
start_dashboard() {
    info "Starting Streamlit dashboard ..."
    exec "$PYTHON" -m streamlit run app.py --server.headless true
}

start_scheduler() {
    info "Starting background scheduler ..."
    exec "$PYTHON" -m src.main
}

start_test() {
    info "Running pipeline once (--test) ..."
    exec "$PYTHON" -m src.main --test
}

start_both() {
    info "Starting scheduler in background + dashboard in foreground ..."
    "$PYTHON" -m src.main &
    SCHEDULER_PID=$!
    ok "Scheduler PID: $SCHEDULER_PID"

    # Trap to clean up scheduler on exit
    trap 'info "Stopping scheduler (PID $SCHEDULER_PID) ..."; kill $SCHEDULER_PID 2>/dev/null; wait $SCHEDULER_PID 2>/dev/null; ok "Done."' EXIT INT TERM

    "$PYTHON" -m streamlit run app.py --server.headless true
}

# ── Main ────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   AI Market Intelligence — Launcher      ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo ""

    activate_venv
    check_deps
    check_env

    MODE="${1:-both}"
    case "$MODE" in
        --dashboard)  start_dashboard ;;
        --scheduler)  start_scheduler ;;
        --test)       start_test ;;
        both|*)       start_both ;;
    esac
}

main "$@"
