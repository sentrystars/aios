#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PROJECT_PATH="$ROOT_DIR/macos/AIOSMac/AIOSMac.xcodeproj"
ARCHIVE_PATH="${ARCHIVE_PATH:-$ROOT_DIR/.build/AIOSMac.xcarchive}"
EXPORT_PATH="${EXPORT_PATH:-$ROOT_DIR/.build/export}"
EXPORT_OPTIONS_PLIST="${EXPORT_OPTIONS_PLIST:-$ROOT_DIR/macos/AIOSMac/ExportOptions.plist}"
DERIVED_DATA_PATH="${DERIVED_DATA_PATH:-$ROOT_DIR/.build/xcode-derived-release}"

if [[ ! -d "$ARCHIVE_PATH" ]]; then
  echo "Archive not found at $ARCHIVE_PATH"
  exit 1
fi

xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportPath "$EXPORT_PATH" \
  -exportOptionsPlist "$EXPORT_OPTIONS_PLIST" \
  -derivedDataPath "$DERIVED_DATA_PATH"
