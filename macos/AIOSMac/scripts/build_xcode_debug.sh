#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PROJECT_PATH="$ROOT_DIR/macos/AIOSMac/AIOSMac.xcodeproj"
DERIVED_DATA_PATH="${DERIVED_DATA_PATH:-$ROOT_DIR/.build/xcode-derived}"

xcodebuild \
  -project "$PROJECT_PATH" \
  -scheme AIOSMac \
  -configuration Debug \
  -derivedDataPath "$DERIVED_DATA_PATH" \
  CODE_SIGNING_ALLOWED=NO \
  build
