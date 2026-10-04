#!/usr/bin/env bash
# ==============================================================================
# JasoForge Distribution Packager
# Builds clean release tar.gz and zip packages
# ==============================================================================

set -euo pipefail

VERSION="5.1.0"
DIST_DIR="dist"
PACKAGE_NAME="jasoforge-v${VERSION}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building release package jasoforge ${VERSION}..."
mkdir -p "${ROOT_DIR}/${DIST_DIR}"

TMP_BUILD="$(mktemp -d)"
STAGE_DIR="${TMP_BUILD}/${PACKAGE_NAME}"
mkdir -p "${STAGE_DIR}"

rsync -av \
    --exclude='.git*' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='scratch' \
    --exclude="${DIST_DIR}" \
    "${ROOT_DIR}/" "${STAGE_DIR}/"

cd "${TMP_BUILD}"

tar -czf "${ROOT_DIR}/${DIST_DIR}/${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}"
echo "✅ Created: ${DIST_DIR}/${PACKAGE_NAME}.tar.gz"

if command -v zip >/dev/null 2>&1; then
    zip -rq "${ROOT_DIR}/${DIST_DIR}/${PACKAGE_NAME}.zip" "${PACKAGE_NAME}"
    echo "✅ Created: ${DIST_DIR}/${PACKAGE_NAME}.zip"
fi

rm -rf "${TMP_BUILD}"
echo "🎉 Distribution build complete!"
