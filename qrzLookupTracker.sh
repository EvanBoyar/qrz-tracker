#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="$SCRIPT_DIR/.secrets"
SENTINEL_FILE="$SCRIPT_DIR/.session_invalid"
LOG_FILE="$SCRIPT_DIR/qrzTracker.log"

# Detect if running in GitHub Actions
CI="${CI:-false}"

log_msg() {
    local level="$1"
    local msg="$2"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    if [ "$CI" = "true" ]; then
        echo "[$ts] [$level] $msg"
    else
        echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE"
    fi
}

notify() {
    local msg="$1"
    if [ "$CI" = "true" ]; then
        # In CI, just log. The workflow handles Issue creation
        log_msg "WARN" "$msg"
    else
        local bus="/run/user/$(id -u)/bus"
        if command -v notify-send &>/dev/null && [ -S "$bus" ]; then
            DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" notify-send "QRZ Tracker" "$msg" 2>/dev/null || true
        fi
    fi
}

# Check for session invalid sentinel (local only)
if [ "$CI" != "true" ] && [ -f "$SENTINEL_FILE" ]; then
    log_msg "WARN" "Session marked invalid. Update .secrets and delete .session_invalid to resume."
    notify "QRZ session expired. Update .secrets and delete .session_invalid"
    exit 0
fi

# Load secrets: prefer environment variables, fall back to .secrets file
if [ -z "${QRZ_SESSION_TOKEN:-}" ] || [ -z "${QRZ_CALLSIGN:-}" ]; then
    if [ -f "$SECRETS_FILE" ]; then
        # shellcheck source=.secrets
        source "$SECRETS_FILE"
    fi
fi

if [ -z "${QRZ_SESSION_TOKEN:-}" ]; then
    log_msg "ERROR" "QRZ_SESSION_TOKEN is not set"
    exit 1
fi

if [ -z "${QRZ_CALLSIGN:-}" ]; then
    log_msg "ERROR" "QRZ_CALLSIGN is not set"
    exit 1
fi

CSV_FILE="$SCRIPT_DIR/${QRZ_CALLSIGN}_QRZ_stats.csv"

# Fetch QRZ page
RESPONSE=$(curl --silent \
    "https://www.qrz.com/db/${QRZ_CALLSIGN}" \
    -H "Cookie: xf_session=${QRZ_SESSION_TOKEN}" \
    -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0")

# Verify session is authenticated. QRZ sets cs_mycs to the callsign when logged in,
# empty string when not. An unauthenticated page view inflates the lookup count.
if echo "$RESPONSE" | grep -q 'var cs_mycs = "";'; then
    log_msg "ERROR" "Session not authenticated. Would inflate lookup count. Halting."
    notify "QRZ session expired. Update token"
    if [ "$CI" != "true" ]; then
        touch "$SENTINEL_FILE"
    fi
    # Exit 2 signals session expiry (workflow uses this to create an Issue)
    exit 2
fi

# Extract lookup count
COUNT=$(echo "$RESPONSE" | grep -oP '(?<=Lookups: )[\d,]+' | tr -d ',')

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP},${COUNT}" >> "$CSV_FILE"
log_msg "INFO" "Recorded: ${COUNT} lookups at ${TIMESTAMP}"

# In CI, the workflow handles viz generation after committing the CSV
if [ "$CI" != "true" ]; then
    "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/qrzHitsViz.py"
fi
