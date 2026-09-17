#!/usr/bin/env bash
# ==============================================================================
# JasoForge Installer for macOS and Linux
# Enterprise-Grade Technical Resume & Engineering Narrative Verification Engine
# ==============================================================================

set -euo pipefail

REPO_URL="https://github.com/choosla/jasoforge"
DEFAULT_BRANCH="main"
TMP_DIR=""

cleanup() {
    if [[ -n "${TMP_DIR:-}" && -d "${TMP_DIR:-}" ]]; then
        rm -rf "${TMP_DIR}"
    fi
}
trap cleanup EXIT

echo "================================================================="
echo "  🔥 JasoForge Installer (macOS & Linux)                        "
echo "  Deterministic Resume Vetting & Engineering Narrative Engine   "
echo "================================================================="

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: python3 is required but not installed." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd || echo "")"

if [[ -n "${SCRIPT_DIR}" && -f "${SCRIPT_DIR}/installer.py" ]]; then
    echo "⚡ Running local installer..."
    python3 "${SCRIPT_DIR}/installer.py" "$@"
else
    echo "🌐 Remote installation detected. Fetching latest JasoForge bundle..."
    TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t 'jasoforge')"
    
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 "${REPO_URL}.git" "${TMP_DIR}/jasoforge" >/dev/null 2>&1
        python3 "${TMP_DIR}/jasoforge/installer.py" "$@"
    else
        TARBALL_URL="${REPO_URL}/archive/refs/heads/${DEFAULT_BRANCH}.tar.gz"
        echo "📥 Downloading tarball from ${TARBALL_URL}..."
        curl -fsSL "${TARBALL_URL}" | tar -xz -C "${TMP_DIR}"
        EXTRACTED_DIR="$(find "${TMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
        python3 "${EXTRACTED_DIR}/installer.py" "$@"
    fi
fi
