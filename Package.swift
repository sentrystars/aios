// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AIOSMac",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(
            name: "AIOSMac",
            targets: ["AIOSMac"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "AIOSMac",
            path: "macos/AIOSMac/Sources"
        ),
    ]
)
