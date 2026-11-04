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
            ],
            // xtool on Linux can't pre-link package targets (lld has no `-r`), so each one (LiveKit.o etc.) is
            // really a static archive. The final link only pulls archive members whose *symbols* are used, which
            // drops Objective-C categories: LiveKit's `Room.add(delegate:)` (@objc, in an extension) went missing
            // and every call crashed with "unrecognized selector addDelegate:". -ObjC loads every member with an
            // ObjC class or category, as Xcode does for static libraries.
            linkerSettings: [.unsafeFlags(["-Xlinker", "-ObjC"])]
        ),
    ]
)
