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

QRZ_CURL_OPTS=(
    --silent
    -H "Cookie: xf_session=${QRZ_SESSION_TOKEN}"
    -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0"
)

# Exit 2 signals session expiry; the workflow uses this to open a tracking issue.
session_expired() {
    log_msg "ERROR" "$1"
    notify "QRZ session expired. Update token"
    if [ "$CI" != "true" ]; then
        touch "$SENTINEL_FILE"
    fi
    exit 2
}

# Probe the homepage first. It does not count toward any callsign's Lookups,
# so bailing here when the session is bad costs us zero inflation. The signal
# is the presence of a /login anchor — QRZ renders it only for logged-out users.
HOME_RESPONSE=$(curl "${QRZ_CURL_OPTS[@]}" "https://www.qrz.com/")
if echo "$HOME_RESPONSE" | grep -qE 'href=["\x27]/login["\x27]'; then
    session_expired "Homepage shows a /login link — session is not authenticated. Skipping profile fetch."
fi

# Profile-page positive check: the page must declare cs_mycs as the tracked
# callsign. Empty, missing, or a different callsign all mean we are not the
# authenticated owner and a recorded count would be inflated by this very hit.
RESPONSE=$(curl "${QRZ_CURL_OPTS[@]}" "https://www.qrz.com/db/${QRZ_CALLSIGN}")
if ! echo "$RESPONSE" | grep -qF "var cs_mycs = \"${QRZ_CALLSIGN}\";"; then
    session_expired "Profile response did not declare cs_mycs=${QRZ_CALLSIGN}."
fi

COUNT=$(echo "$RESPONSE" | grep -oP '(?<=Lookups: )[\d,]+' | tr -d ',')

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP},${COUNT}" >> "$CSV_FILE"
log_msg "INFO" "Recorded: ${COUNT} lookups at ${TIMESTAMP}"

# In CI, the workflow handles viz generation after committing the CSV
if [ "$CI" != "true" ]; then
    "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/qrzHitsViz.py"
fi
