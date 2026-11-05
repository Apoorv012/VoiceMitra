import SwiftUI

/// SPEC I5 (and the I4 fallback ring): full screen while a call is ringing in-app, connecting or live.
struct CallScreen: View {
    @Environment(AppModel.self) private var model

    private var calls: CallCenter { model.calls }
    @State private var pulse = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            ZStack {
                // Soft rings that breathe while ringing / connecting, and settle once live.
                ForEach(0..<3) { i in
                    Circle()
                        .fill(Color(UIColor(hex: 0x8FBC72)).opacity(0.10))
                        .frame(width: 130 + CGFloat(i) * 46, height: 130 + CGFloat(i) * 46)
                        .scaleEffect(pulse && calls.phase != .live ? 1.08 : 1)
                        .animation(.easeInOut(duration: 1.2).repeatForever().delay(Double(i) * 0.2), value: pulse)
                }
                RoundedRectangle(cornerRadius: 34, style: .continuous)
                    .fill(Color(UIColor(hex: 0x8FBC72)))
                    .frame(width: 120, height: 120)
                    .overlay {
                        Image(systemName: "mic.fill")
                            .font(.system(size: 54, weight: .semibold))
                            .foregroundStyle(Color(UIColor(hex: 0x0C1A0A)))
                    }
            }
            .frame(height: 240)
            .onAppear { pulse = true }
            Text("VoiceMitra")
                .font(.system(size: 40, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
            status
                .font(.title2.weight(.semibold))
                .foregroundStyle(.white.opacity(0.85))
            Spacer()
            if calls.inAppRinging {
                ringingButtons
            } else {
                callButtons
            }
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            LinearGradient(colors: [Color(UIColor(hex: 0x1F2E19)), Color(UIColor(hex: 0x0C110C))],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
        )
        .interactiveDismissDisabled()
    }

    @ViewBuilder private var status: some View {
        switch calls.phase {
        case .ringing:
            Text(model.t("is calling you…", "आपको कॉल कर रहा है…"))
        case .connecting:
            HStack(spacing: 10) {
                ProgressView().tint(.white)
                Text(model.t("Connecting…", "जोड़ा जा रहा है…"))
            }
        case .live:
            VStack(spacing: 10) {
                if let start = calls.connectedAt {
                    TimelineView(.periodic(from: start, by: 1)) { ctx in
                        Text(Self.elapsed(from: start, to: ctx.date)).monospacedDigit()
                    }
                }
                Text(model.t("Connected. Speak after VoiceMitra greets you.", "जुड़ गए। VoiceMitra के नमस्ते के बाद बोलें।"))
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.75))
                    .multilineTextAlignment(.center)
            }
        case .idle:
            EmptyView()
        }
    }

    private var ringingButtons: some View {
        HStack(spacing: 48) {
            RoundButton(icon: "phone.down.fill", label: model.t("Decline", "मना करें"), color: .red) {
                calls.declineInApp()
            }
            RoundButton(icon: "phone.fill", label: model.t("Answer", "उठाएँ"), color: .green) {
                calls.answerInApp()
            }
        }
    }

    private var callButtons: some View {
        VStack(spacing: 32) {
            HStack(spacing: 48) {
                RoundButton(icon: calls.isMuted ? "mic.slash.fill" : "mic.fill",
                            label: calls.isMuted ? model.t("Unmute", "माइक चालू") : model.t("Mute", "माइक बंद"),
                            color: calls.isMuted ? .white : .white.opacity(0.25),
                            iconColor: calls.isMuted ? .black : .white) {
                    calls.toggleMute()
                }
                RoundButton(icon: calls.isSpeaker ? "speaker.wave.3.fill" : "iphone",
                            label: calls.isSpeaker ? model.t("Speaker", "स्पीकर") : model.t("Phone", "फ़ोन"),
                            color: calls.isSpeaker ? .white : .white.opacity(0.25),
                            iconColor: calls.isSpeaker ? .black : .white) {
                    calls.toggleSpeaker()
                }
            }
            RoundButton(icon: "phone.down.fill", label: model.t("End call", "कॉल खत्म करें"), color: .red, size: 96) {
                calls.hangUp()
            }
        }
    }

    static func elapsed(from start: Date, to now: Date) -> String {
        let s = max(0, Int(now.timeIntervalSince(start)))
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

private struct RoundButton: View {
    let icon: String
    let label: String
    let color: Color
    var iconColor: Color = .white
    var size: CGFloat = 80
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: size * 0.4, weight: .bold))
                    .foregroundStyle(iconColor)
                    .frame(width: size, height: size)
                    .background(Circle().fill(color))
                Text(label)
                    .font(.headline)
                    .foregroundStyle(.white)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}
