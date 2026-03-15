#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_NAME="comfy"
DESKTOP_FILE="${PLUGIN_NAME}.desktop"
PLUGIN_DIR="${PLUGIN_NAME}"
DIST_DIR="${ROOT_DIR}/dist"
STAGING_DIR="${DIST_DIR}/.package-staging"
ARCHIVE_PATH="${DIST_DIR}/${PLUGIN_NAME}-krita-plugin.zip"

if [[ ! -f "${ROOT_DIR}/${DESKTOP_FILE}" ]]; then
    echo "Missing desktop file: ${DESKTOP_FILE}" >&2
    exit 1
fi

if [[ ! -d "${ROOT_DIR}/${PLUGIN_DIR}" ]]; then
    echo "Missing plugin directory: ${PLUGIN_DIR}" >&2
    exit 1
fi

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}" "${DIST_DIR}"

cp "${ROOT_DIR}/${DESKTOP_FILE}" "${STAGING_DIR}/${DESKTOP_FILE}"

rsync -a \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.pyo' \
    --exclude '.DS_Store' \
    "${ROOT_DIR}/${PLUGIN_DIR}/" "${STAGING_DIR}/${PLUGIN_DIR}/"

rm -f "${ARCHIVE_PATH}"

(
    cd "${STAGING_DIR}"
    zip -r "${ARCHIVE_PATH}" "${DESKTOP_FILE}" "${PLUGIN_DIR}" >/dev/null
)

rm -rf "${STAGING_DIR}"

echo "Created package: ${ARCHIVE_PATH}"
