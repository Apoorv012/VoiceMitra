import SwiftUI

@main
struct VoiceMitraApp: App {
    @State private var model = AppModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .environment(\.locale, Locale(identifier: model.lang == .hi ? "hi_IN" : "en_IN"))
        }
        // `.inactive` also happens while CallKit's ringing banner is up; the socket must stay open then, or a
        // voice_call_ended (the caller gave up) would be missed and the phone would keep ringing.
        .onChange(of: scenePhase, initial: true) { _, phase in
            model.setActive(phase != .background)
        }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Group {
            if model.pairing == nil {
                PairingView()
            } else {
                HomeView()
            }
        }
        // While CallKit rings, its own screen/banner has the answer buttons; ours shows from then on.
        .fullScreenCover(isPresented: .constant(showCallScreen)) {
            CallScreen()
                .environment(model)
        }
    }

    private var showCallScreen: Bool {
        switch model.calls.phase {
        case .idle: false
        case .ringing: model.calls.inAppRinging
        case .connecting, .live: true
        }
    }
}

// MARK: - Shared formatting

@MainActor
enum Fmt {
    static func time(_ date: Date, tz: String?, lang: Lang) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: lang == .hi ? "hi_IN" : "en_IN")
        f.timeZone = TimeZone(identifier: tz ?? "Asia/Kolkata") ?? .current
        f.dateFormat = "h:mm a"
        return f.string(from: date)
    }

    static func greeting(tz: String?, model: AppModel) -> String {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: tz ?? "Asia/Kolkata") ?? .current
        let hour = cal.component(.hour, from: Date())
        if hour < 12 { return model.t("Good morning", "सुप्रभात") }
        if hour < 17 { return model.t("Good afternoon", "नमस्कार") }
        return model.t("Good evening", "शुभ संध्या")
    }

    /// Dose states, same words as the web app (web/src/lib/i18n.tsx).
    static func state(_ s: String, _ model: AppModel) -> (label: String, color: Color, icon: String) {
        switch s {
        case "taken": return (model.t("Taken", "ले ली"), .green, "checkmark.circle.fill")
        case "partial": return (model.t("Partly taken", "आधी ली"), .orange, "circle.lefthalf.filled")
        case "missed": return (model.t("Missed", "छूट गई"), .red, "xmark.circle.fill")
        case "later": return (model.t("Taking later", "बाद में लेंगे"), .orange, "clock.fill")
        case "unknown": return (model.t("Not sure", "पक्का नहीं"), .gray, "questionmark.circle.fill")
        case "skipped": return (model.t("Skipped on advice", "सलाह पर छोड़ी"), .gray, "minus.circle.fill")
        case "due": return (model.t("Due now", "अभी लेनी है"), .blue, "bell.fill")
        case "no_checkin": return (model.t("Not checked", "पूछा नहीं गया"), .gray, "circle.dashed")
        default: return (model.t("Upcoming", "आने वाली"), .secondary, "circle")
        }
    }
}
