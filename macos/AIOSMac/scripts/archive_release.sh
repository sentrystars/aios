#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PROJECT_PATH="$ROOT_DIR/macos/AIOSMac/AIOSMac.xcodeproj"
ARCHIVE_PATH="${ARCHIVE_PATH:-$ROOT_DIR/.build/AIOSMac.xcarchive}"
DERIVED_DATA_PATH="${DERIVED_DATA_PATH:-$ROOT_DIR/.build/xcode-derived-release}"
DEVELOPMENT_TEAM="${DEVELOPMENT_TEAM:-}"

if [[ -z "$DEVELOPMENT_TEAM" ]]; then
  echo "DEVELOPMENT_TEAM is required for a signed archive."
  exit 1
fi

xcodebuild \
  -project "$PROJECT_PATH" \
  -scheme AIOSMac \
  -configuration Release \
  -archivePath "$ARCHIVE_PATH" \
  -derivedDataPath "$DERIVED_DATA_PATH" \
  DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM" \
  archive
