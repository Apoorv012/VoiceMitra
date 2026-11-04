// swift-tools-version: 6.1
// The VoiceMitra iPhone app, built with xtool (see ../README.md). xtool packages the `VoiceMitra` library
// product as the app; Info.plist additions live in Support/Info.plist (merged by xtool, see xtool.yml).
import PackageDescription

let package = Package(
    name: "VoiceMitra",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "VoiceMitra", targets: ["VoiceMitra"]),
    ],
    dependencies: [
        .package(url: "https://github.com/livekit/client-sdk-swift.git", from: "2.19.0"),
    ],
    targets: [
        .target(
            name: "VoiceMitra",
            dependencies: [.product(name: "LiveKit", package: "client-sdk-swift")],
            swiftSettings: [
                .swiftLanguageMode(.v5),
                // The "pick a patient" list (no pairing) only exists in debug builds (xtool dev).
                .define("DEV_PICKER", .when(configuration: .debug)),
            ]
        ),
    ]
)
