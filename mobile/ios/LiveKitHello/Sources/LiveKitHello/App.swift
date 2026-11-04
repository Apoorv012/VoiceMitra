import LiveKit
import SwiftUI

@main
struct LiveKitHelloApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

struct ContentView: View {
    // Creating a Room pulls in the WebRTC framework at runtime, so a crash here means it didn't embed/sign.
    @State private var room = Room()

    var body: some View {
        VStack(spacing: 16) {
            Text("VoiceMitra toolchain check").font(.title2.bold())
            Text("LiveKit SDK \(LiveKitSDK.version)")
            Text("Room state: \(String(describing: room.connectionState))")
                .foregroundStyle(.secondary)
        }
        .padding()
    }
}
