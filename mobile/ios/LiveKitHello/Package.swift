// swift-tools-version: 6.1
// I1 toolchain probe: the smallest app that links the LiveKit Swift SDK (and its WebRTC binary framework).
import PackageDescription

let package = Package(
    name: "LiveKitHello",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "LiveKitHello", targets: ["LiveKitHello"]),
    ],
    dependencies: [
        .package(url: "https://github.com/livekit/client-sdk-swift.git", from: "2.19.0"),
    ],
    targets: [
        .target(
            name: "LiveKitHello",
            dependencies: [.product(name: "LiveKit", package: "client-sdk-swift")]
        ),
    ]
)
