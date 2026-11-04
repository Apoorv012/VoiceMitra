import SwiftUI

/// SPEC I3: greeting, next medicine, today's doses, the big "Talk to VoiceMitra" button.
struct HomeView: View {
    @Environment(AppModel.self) private var model
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header
                    if let error = model.calls.error {
                        Banner(text: error, color: .red) { model.calls.error = nil }
                    }
                    talkButton
                    if let home = model.home {
                        if let next = home.nextDose { NextDoseCard(slot: next, tz: home.timezone) }
                        TodayCard(home: home)
                        if let how = home.howDoing { HowDoingCard(how: how) }
                        if !home.reminders.isEmpty { RemindersCard(home: home) }
                    } else if let error = model.homeError {
                        Banner(text: error, color: .orange) { Task { await model.loadHome() } }
                    } else {
                        ProgressView().frame(maxWidth: .infinity).padding(.top, 40)
                    }
                    if !model.socketConnected {
                        Label(model.t("Not connected: VoiceMitra can't ring this phone right now.",
                                      "जुड़ा नहीं है: अभी VoiceMitra इस फ़ोन पर कॉल नहीं कर सकता।"),
                              systemImage: "wifi.exclamationmark")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    Text(model.t("Keep VoiceMitra open to receive its calls.", "VoiceMitra की कॉल पाने के लिए ऐप खुला रखें।"))
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                .padding(20)
            }
            .refreshable { await model.loadHome() }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { LanguageToggle() }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                        .accessibilityLabel(model.t("Settings", "सेटिंग्स"))
                }
            }
            .sheet(isPresented: $showSettings) { SettingsView() }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(Fmt.greeting(tz: model.home?.timezone, model: model))
                .font(.title3)
                .foregroundStyle(.secondary)
            Text(model.t("Hello, \(firstName)", "नमस्ते, \(firstName)"))
                .font(.largeTitle.bold())
        }
        .accessibilityElement(children: .combine)
    }

    private var firstName: String {
        let name = model.home?.patient.name ?? model.pairing?.patientName ?? ""
        return name.split(separator: " ").first.map(String.init) ?? name
    }

    private var talkButton: some View {
        Button {
            Task { await model.talkNow() }
        } label: {
            VStack(spacing: 6) {
                Image(systemName: "phone.fill").font(.system(size: 40, weight: .bold))
                Text(model.talkBusy ? model.t("Starting…", "शुरू हो रहा है…") : model.t("Talk to VoiceMitra", "VoiceMitra से बात करें"))
                    .font(.title.bold())
                    .multilineTextAlignment(.center)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 130)
            .background(RoundedRectangle(cornerRadius: 24).fill(Color(red: 0.0, green: 0.42, blue: 0.24)))
        }
        .buttonStyle(.plain)
        .disabled(model.talkBusy || model.calls.phase != .idle)
        .accessibilityHint(model.t("Starts a short check-in call", "छोटी-सी बातचीत शुरू करता है"))
    }
}

private struct Card<Content: View>: View {
    let title: String
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.title2.bold())
            content
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 18).fill(Color(.secondarySystemBackground)))
    }
}

private struct NextDoseCard: View {
    @Environment(AppModel.self) private var model
    let slot: Slot
    let tz: String

    var body: some View {
        Card(title: model.t("Next dose", "अगली दवा")) {
            Text(Fmt.time(slot.at, tz: tz, lang: model.lang))
                .font(.system(.largeTitle, design: .rounded).bold())
            Text("\(slot.medicine) · \(slot.dose)").font(.title3)
        }
    }
}

private struct TodayCard: View {
    @Environment(AppModel.self) private var model
    let home: PatientHome

    var body: some View {
        Card(title: model.t("Today's medicines", "आज की दवाइयाँ")) {
            if home.today.isEmpty {
                Text(model.t("No medicines are scheduled for today.", "आज कोई दवा तय नहीं है।")).font(.title3)
            }
            ForEach(home.today) { slot in
                let s = Fmt.state(slot.state, model)
                HStack(alignment: .top, spacing: 12) {
                    Text(Fmt.time(slot.at, tz: home.timezone, lang: model.lang))
                        .font(.title3.monospacedDigit().bold())
                        .frame(minWidth: 90, alignment: .leading)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(slot.medicine).font(.title3.weight(.semibold))
                        Text(slot.dose).font(.body).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 8)
                    Label(s.label, systemImage: s.icon)
                        .font(.body.weight(.semibold))
                        .foregroundStyle(s.color)
                        .multilineTextAlignment(.trailing)
                }
                .accessibilityElement(children: .combine)
                if slot.id != home.today.last?.id { Divider() }
            }
        }
    }
}

private struct HowDoingCard: View {
    @Environment(AppModel.self) private var model
    let how: HowDoing

    var body: some View {
        Card(title: model.t("How you're doing", "आपकी सेहत")) {
            Text(how.summary).font(.title3)
        }
    }
}

private struct RemindersCard: View {
    @Environment(AppModel.self) private var model
    let home: PatientHome

    var body: some View {
        Card(title: model.t("Calls coming up", "आने वाली कॉल")) {
            ForEach(home.reminders, id: \.self) { at in
                let time = Fmt.time(at, tz: home.timezone, lang: model.lang)
                Label(model.t("VoiceMitra will call you at \(time)", "VoiceMitra आपको \(time) पर कॉल करेगा"),
                      systemImage: "phone.arrow.down.left")
                    .font(.title3)
            }
        }
    }
}

struct Banner: View {
    let text: String
    let color: Color
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top) {
                Image(systemName: "exclamationmark.triangle.fill")
                Text(text).multilineTextAlignment(.leading)
                Spacer()
            }
            .font(.body.weight(.semibold))
            .foregroundStyle(color)
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 14).stroke(color, lineWidth: 2))
        }
        .buttonStyle(.plain)
    }
}
