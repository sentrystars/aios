# AIOSMac

Native macOS client for the existing AI OS FastAPI backend.

## Current scope

- overview dashboard for `/self`, `/tasks`, `/events`
- task list + detail pane
- create task sheet
- plan / start task actions
- backend URL configurable from app settings

## Run

Start the backend first:

```bash
uvicorn main:app --reload --port 8787
```

Then build or run the macOS app from the repository root:

```bash
swift build
swift run AIOSMac
```

## Xcode

You can also open the native Xcode project directly:

```bash
open macos/AIOSMac/AIOSMac.xcodeproj
```

Verified locally with:

```bash
xcodebuild -project macos/AIOSMac/AIOSMac.xcodeproj -scheme AIOSMac -configuration Debug -derivedDataPath .build/xcode-derived CODE_SIGNING_ALLOWED=NO build
```

## Packaging

Debug build:

```bash
./macos/AIOSMac/scripts/build_xcode_debug.sh
```

Signed release archive:

```bash
DEVELOPMENT_TEAM=YOURTEAMID ./macos/AIOSMac/scripts/archive_release.sh
```

Export from archive:

```bash
./macos/AIOSMac/scripts/export_archive.sh
```

Before export, replace `TEAMID_PLACEHOLDER` in [ExportOptions.plist](/Users/liuxiaofeng/AI OS/macos/AIOSMac/ExportOptions.plist) with your real Apple team ID and adjust the export method if you are shipping through a different channel.
