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
                .tint(VM.accent)
                .fontDesign(.rounded)
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
                SignInView()
                    .transition(.opacity)
            } else {
                MainTabs()
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: model.pairing == nil)
        // While CallKit rings, its own screen/banner has the answer buttons; ours shows from then on.
        .fullScreenCover(isPresented: .constant(showCallScreen)) {
            CallScreen()
                .environment(model)
                .fontDesign(.rounded)
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

struct MainTabs: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        TabView {
            TodayView().tabItem { Label(model.t("Today", "आज"), systemImage: "house.fill") }
            MedicinesView().tabItem { Label(model.t("Medicines", "दवाइयाँ"), systemImage: "pills.fill") }
            HistoryView().tabItem { Label(model.t("History", "इतिहास"), systemImage: "clock.arrow.circlepath") }
            MeView().tabItem { Label(model.t("Me", "मैं"), systemImage: "person.crop.circle.fill") }
        }
    }
}

/// A scrolling tab page on the page colour, with the app header on top.
struct TabPage<Content: View>: View {
    var refresh: (() async -> Void)?
    @ViewBuilder var content: Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                AppHeader()
                content
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .background(VM.page.ignoresSafeArea())
        .refreshable { await refresh?() }
    }
}

// MARK: - Shared formatting

@MainActor
enum Fmt {
    static func zone(_ tz: String?) -> TimeZone { TimeZone(identifier: tz ?? "Asia/Kolkata") ?? .current }

    static func locale(_ lang: Lang) -> Locale { Locale(identifier: lang == .hi ? "hi_IN" : "en_IN") }

    static func time(_ date: Date, tz: String?, lang: Lang) -> String {
        let f = DateFormatter()
        f.locale = locale(lang)
        f.timeZone = zone(tz)
        f.dateFormat = "h:mm a"
        return f.string(from: date)
    }

    /// "Today" / "Yesterday" / "Mon, 3 Nov".
    static func day(_ date: Date, tz: String?, model: AppModel) -> String {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zone(tz)
        if cal.isDateInToday(date) { return model.t("Today", "आज") }
        if cal.isDateInYesterday(date) { return model.t("Yesterday", "कल") }
        if cal.isDateInTomorrow(date) { return model.t("Tomorrow", "कल") }
        let f = DateFormatter()
        f.locale = locale(model.lang)
        f.timeZone = zone(tz)
        f.dateFormat = "EEE, d MMM"
        return f.string(from: date)
    }

    /// "Today, 9:00 PM"
    static func when(_ date: Date, tz: String?, model: AppModel) -> String {
        "\(day(date, tz: tz, model: model)), \(time(date, tz: tz, lang: model.lang))"
    }

    /// "in 2 h" / "in 25 min" / "now"; nil when it's in the past.
    static func relative(_ date: Date, model: AppModel) -> String? {
        let mins = Int(date.timeIntervalSinceNow / 60)
        if mins < -5 { return nil }
        if mins <= 1 { return model.t("now", "अभी") }
        if mins < 60 { return model.t("in \(mins) min", "\(mins) मिनट में") }
        let h = Int((Double(mins) / 60).rounded())
        return model.t("in \(h) h", "\(h) घंटे में")
    }

    /// "GOOD EVENING · WEDNESDAY, 4 NOVEMBER"
    static func dateLine(tz: String?, model: AppModel) -> String {
        let f = DateFormatter()
        f.locale = locale(model.lang)
        f.timeZone = zone(tz)
        f.dateFormat = "EEEE, d MMMM"
        return "\(greeting(tz: tz, model: model)) · \(f.string(from: Date()))"
    }

    static func greeting(tz: String?, model: AppModel) -> String {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zone(tz)
        let hour = cal.component(.hour, from: Date())
        if hour < 12 { return model.t("Good morning", "सुप्रभात") }
        if hour < 17 { return model.t("Good afternoon", "नमस्कार") }
        return model.t("Good evening", "शुभ संध्या")
    }

    /// "09:00" -> "9:00 AM"
    static func clock(_ hhmm: String, lang: Lang) -> String {
        let parts = hhmm.split(separator: ":").compactMap { Int($0) }
        guard parts.count >= 2 else { return hhmm }
        var c = DateComponents()
        c.hour = parts[0]
        c.minute = parts[1]
        guard let d = Calendar(identifier: .gregorian).date(from: c) else { return hhmm }
        let f = DateFormatter()
        f.locale = locale(lang)
        f.dateFormat = "h:mm a"
        return f.string(from: d)
    }

    static func list(_ items: [String], model: AppModel) -> String {
        guard items.count > 1 else { return items.first ?? "" }
        return items.dropLast().joined(separator: ", ") + " \(model.t("and", "और")) " + items.last!
    }

    /// "Every day at 9:00 AM and 9:00 PM" (same words as the web's medicine cards).
    static func schedule(_ m: MedicineView, model: AppModel) -> String {
        let times = list(m.times.map { clock($0, lang: model.lang) }, model: model)
        switch m.frequency {
        case "weekly": return model.t("Once a week at \(times)", "हफ़्ते में एक बार, \(times)")
        case "every_x_day":
            let n = m.intervalDays ?? 1
            return model.t("Every \(n) days at \(times)", "हर \(n) दिन, \(times)")
        case "fixed_times": return model.t("At \(times)", "\(times) पर")
        default: return model.t("Every day at \(times)", "रोज़ \(times)")
        }
    }

    struct Status {
        let label: String
        let icon: String
        let ink: Color
        let soft: Color
    }

    /// Dose states, same words as the web app (web/src/lib/i18n.tsx).
    static func state(_ s: String, _ model: AppModel) -> Status {
        switch s {
        case "taken": return Status(label: model.t("Taken", "ले ली"), icon: "checkmark", ink: VM.goodInk, soft: VM.goodSoft)
        case "partial": return Status(label: model.t("Partly taken", "आधी ली"), icon: "circle.lefthalf.filled", ink: VM.warnInk, soft: VM.warnSoft)
        case "missed": return Status(label: model.t("Missed", "छूट गई"), icon: "xmark", ink: VM.critInk, soft: VM.critSoft)
        case "later": return Status(label: model.t("Taking later", "बाद में लेंगे"), icon: "clock", ink: VM.warnInk, soft: VM.warnSoft)
        case "unknown": return Status(label: model.t("Not sure", "पक्का नहीं"), icon: "questionmark", ink: VM.ink2, soft: VM.neutralSoft)
        case "skipped": return Status(label: model.t("Skipped on advice", "सलाह पर छोड़ी"), icon: "minus", ink: VM.ink2, soft: VM.neutralSoft)
        case "due": return Status(label: model.t("Due now", "अभी लेनी है"), icon: "bell.fill", ink: VM.onBtn, soft: VM.accent)
        case "no_checkin": return Status(label: model.t("Not checked", "पूछा नहीं गया"), icon: "circle.dashed", ink: VM.ink2, soft: VM.neutralSoft)
        default: return Status(label: model.t("Upcoming", "आने वाली"), icon: "clock", ink: VM.ink2, soft: VM.neutralSoft)
        }
    }

    static func medicineStatus(_ s: String?, _ model: AppModel) -> Status? {
        switch s {
        case "taken": return Status(label: model.t("Medicine taken", "दवा ली"), icon: "checkmark", ink: VM.goodInk, soft: VM.goodSoft)
        case "not_taken": return Status(label: model.t("Medicine not taken", "दवा नहीं ली"), icon: "xmark", ink: VM.critInk, soft: VM.critSoft)
        case "confusion", "dont_know": return Status(label: model.t("Unsure about medicine", "दवा के बारे में पक्का नहीं"), icon: "questionmark", ink: VM.warnInk, soft: VM.warnSoft)
        default: return nil
        }
    }

    static func band(_ band: String, _ model: AppModel) -> Status {
        switch band {
        case "urgent": return Status(label: model.t("Needs a doctor's attention", "डॉक्टर को दिखाना ज़रूरी है"), icon: "exclamationmark.triangle.fill", ink: VM.critInk, soft: VM.critSoft)
        case "watch": return Status(label: model.t("Worth telling your doctor", "डॉक्टर को बताना ठीक रहेगा"), icon: "exclamationmark.circle.fill", ink: VM.warnInk, soft: VM.warnSoft)
        default: return Status(label: model.t("Looks fine", "सब ठीक लगा"), icon: "checkmark.circle.fill", ink: VM.goodInk, soft: VM.goodSoft)
        }
    }
}
