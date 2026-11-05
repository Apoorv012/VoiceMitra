import SwiftUI

/// The Today tab (SPEC I3, the web's patient home): greeting, the check-in card with the big Talk button, next
/// dose, today's medicines, the week, how they're doing, calls coming up.
struct TodayView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        TabPage(refresh: { await model.loadHome() }) {
            header
            if let error = model.calls.error {
                Notice(text: error, icon: "exclamationmark.circle.fill", ink: VM.critInk, soft: VM.critSoft) {
                    model.calls.error = nil
                }
            }
            CheckInCard()
            if let home = model.home {
                if let next = home.nextDose { NextDoseCard(slot: next, tz: home.timezone) }
                TodayMedsCard(home: home)
                WeekCard(home: home)
                if let how = home.howDoing { HowDoingCard(how: how) }
                if !home.reminders.isEmpty { RemindersCard(home: home) }
                if let cg = home.caregiver {
                    Label(model.t("\(cg.name) (\(cg.relation)) is told if we can't reach you or you're not feeling well.",
                                  "अगर आपसे बात न हो सके या आपकी तबीयत ठीक न हो, तो \(cg.name) (\(cg.relation)) को बताया जाता है।"),
                          systemImage: "heart.fill")
                        .font(.subheadline)
                        .foregroundStyle(VM.muted)
                        .padding(.horizontal, 4)
                }
                if model.homeError != nil {
                    Label(model.t("Couldn't refresh. Showing what we had.", "ताज़ा नहीं हो सका। पहले की जानकारी दिखा रहे हैं।"),
                          systemImage: "arrow.clockwise")
                        .font(.footnote)
                        .foregroundStyle(VM.muted)
                }
            } else if let error = model.homeError {
                Notice(text: error, icon: "wifi.exclamationmark", ink: VM.warnInk, soft: VM.warnSoft) {
                    Task { await model.loadHome() }
                }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            }
            ConnectionLine()
        }
        .task { await model.askForMicrophone() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Eyebrow(text: Fmt.dateLine(tz: model.home?.timezone, model: model))
            Text(model.t("Hello, \(firstName)", "नमस्ते, \(firstName)"))
                .font(.largeTitle.bold())
                .foregroundStyle(VM.ink)
                .accessibilityAddTraits(.isHeader)
        }
        .padding(.top, 6)
        .accessibilityElement(children: .combine)
    }

    private var firstName: String {
        let name = model.home?.patient.name ?? model.pairing?.patientName ?? ""
        return name.split(separator: " ").first.map(String.init) ?? name
    }
}

/// "Talk to VoiceMitra" -- the main action, on the sage tint like the web.
private struct CheckInCard: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                IconBadge(systemName: "waveform", tint: VM.onBtn, fill: VM.btn, size: 52)
                VStack(alignment: .leading, spacing: 2) {
                    Text(model.t("Talk to VoiceMitra", "VoiceMitra से बात करें"))
                        .font(.title2.bold())
                        .foregroundStyle(VM.ink)
                    Text(model.t("A quick check-in takes about 2 minutes.", "छोटी-सी बातचीत में लगभग 2 मिनट लगते हैं।"))
                        .font(.body)
                        .foregroundStyle(VM.ink2)
                }
            }
            Button {
                Task { await model.talkNow() }
            } label: {
                HStack(spacing: 10) {
                    if model.talkBusy {
                        ProgressView().tint(VM.onBtn)
                    } else {
                        Image(systemName: "phone.fill")
                    }
                    Text(model.talkBusy ? model.t("Starting…", "शुरू हो रहा है…") : model.t("Start check-in", "बातचीत शुरू करें"))
                }
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(model.talkBusy || model.calls.phase != .idle)

            if let home = model.home {
                Group {
                    if let last = home.lastCheckin {
                        Text(model.t("Last check-in \(Fmt.when(last.at, tz: home.timezone, model: model))",
                                     "पिछली बातचीत \(Fmt.when(last.at, tz: home.timezone, model: model))"))
                    } else {
                        Text(model.t("No check-ins yet", "अभी तक कोई बातचीत नहीं हुई"))
                    }
                }
                .font(.footnote)
                .foregroundStyle(VM.ink2)
            }
        }
        .card(fill: VM.sage, stroke: nil, padding: 22)
    }
}

private struct NextDoseCard: View {
    @Environment(AppModel.self) private var model
    let slot: Slot
    let tz: String

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            IconBadge(systemName: "pills.fill", tint: VM.accent, fill: VM.surface)
            VStack(alignment: .leading, spacing: 4) {
                Eyebrow(text: model.t("Next dose", "अगली दवा"), color: VM.accent)
                Text("\(slot.medicine)")
                    .font(.title3.bold())
                    .foregroundStyle(VM.ink)
                + Text(" · \(slot.dose)").font(.body).foregroundStyle(VM.ink2)
                Text([Fmt.when(slot.at, tz: tz, model: model),
                      slot.state == "due" ? nil : Fmt.relative(slot.at, model: model)].compactMap { $0 }.joined(separator: " · "))
                    .font(.body.weight(.medium))
                    .foregroundStyle(VM.accent)
            }
            Spacer(minLength: 0)
        }
        .card(fill: VM.accentSoft, stroke: nil)
        .accessibilityElement(children: .combine)
    }
}

private struct TodayMedsCard: View {
    @Environment(AppModel.self) private var model
    let home: PatientHome

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(model.t("Today's medicines", "आज की दवाइयाँ"))
                .font(.title3.bold())
                .foregroundStyle(VM.ink)
                .padding(.bottom, 12)
            if home.today.isEmpty {
                Text(model.t("No medicines are scheduled for today.", "आज कोई दवा तय नहीं है।"))
                    .font(.body)
                    .foregroundStyle(VM.muted)
            }
            ForEach(Array(home.today.enumerated()), id: \.element.id) { i, slot in
                let s = Fmt.state(slot.state, model)
                // Time on the left, then name / dose / status stacked, so long names and big text never squeeze.
                HStack(alignment: .top, spacing: 14) {
                    Text(Fmt.time(slot.at, tz: home.timezone, lang: model.lang))
                        .font(.headline.monospacedDigit())
                        .foregroundStyle(VM.ink)
                        .fixedSize()
                        .padding(.top, 1)
                    VStack(alignment: .leading, spacing: 6) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(slot.medicine).font(.headline).foregroundStyle(VM.ink)
                            Text(slot.dose).font(.subheadline).foregroundStyle(VM.muted)
                        }
                        StatusPill(label: s.label, icon: s.icon, ink: s.ink, soft: s.soft)
                    }
                    Spacer(minLength: 0)
                }
                .padding(.vertical, 12)
                .accessibilityElement(children: .combine)
                if i < home.today.count - 1 { Divider().overlay(VM.line) }
            }
        }
        .card()
    }
}

/// Seven day dots (the web's "This week"), coloured by how the day went, plus the count.
private struct WeekCard: View {
    @Environment(AppModel.self) private var model
    let home: PatientHome

    var body: some View {
        let a = home.adherence
        let total = a.taken + a.missed + a.unrecorded
        let anyScheduled = home.week.contains { $0.state != "none" }
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text(model.t("This week", "इस हफ़्ते")).font(.title3.bold()).foregroundStyle(VM.ink)
                Spacer()
                if let rate = a.rate, anyScheduled {
                    Text("\(rate)%").font(.title3.bold().monospacedDigit()).foregroundStyle(VM.accent)
                }
            }
            if anyScheduled {
                HStack(spacing: 4) {
                    ForEach(home.week) { day in
                        let today = isToday(day.date)
                        VStack(spacing: 6) {
                            Text(weekday(day.date))
                                .font(.caption.weight(today ? .heavy : .semibold))
                                .foregroundStyle(today ? VM.ink : VM.muted)
                            dot(day.state)
                                .overlay { if today { Circle().strokeBorder(VM.ink, lineWidth: 2).padding(-4) } }
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(model.t("This week", "इस हफ़्ते"))
                if total > 0 {
                    Text(model.t("\(a.taken) of \(total) doses taken", "\(total) में से \(a.taken) खुराकें ली गईं"))
                        .font(.body.weight(.medium))
                        .foregroundStyle(VM.ink2)
                }
                legend
                if a.unrecorded > 0 {
                    Text(model.t("\(a.unrecorded) not checked", "\(a.unrecorded) के बारे में पूछा नहीं गया"))
                        .font(.footnote)
                        .foregroundStyle(VM.muted)
                }
            } else {
                Text(model.t("Nothing was scheduled this week.", "इस हफ़्ते कुछ तय नहीं था।"))
                    .font(.body)
                    .foregroundStyle(VM.muted)
            }
        }
        .card()
    }

    /// The web's WeekLegend: what each dot means (icon + word, never colour alone).
    private var legend: some View {
        let items: [(String, String)] = [
            ("good", model.t("All taken", "सब ली")), ("mixed", model.t("Some missed", "कुछ छूटीं")),
            ("missed", model.t("Missed", "छूट गईं")), ("unknown", model.t("Not checked", "पूछा नहीं गया")),
        ]
        let columns = [GridItem(.adaptive(minimum: 140), alignment: .leading)]
        return LazyVGrid(columns: columns, alignment: .leading, spacing: 8) {
            ForEach(items, id: \.0) { state, word in
                HStack(spacing: 8) {
                    dot(state, size: 22)
                    Text(word).font(.footnote).foregroundStyle(VM.ink2)
                }
            }
        }
    }

    private func isToday(_ iso: String) -> Bool {
        let p = DateFormatter()
        p.dateFormat = "yyyy-MM-dd"
        p.timeZone = Fmt.zone(home.timezone)
        return p.string(from: Date()) == iso
    }

    private func dot(_ state: String, size: CGFloat = 36) -> some View {
        let (fill, icon, ink): (Color, String?, Color) = switch state {
        case "good": (VM.good, "checkmark", VM.onBtn)
        case "mixed": (VM.warnSoft, "circle.lefthalf.filled", VM.warnInk)
        case "missed": (VM.critSoft, "xmark", VM.critInk)
        case "unknown": (VM.neutralSoft, "questionmark", VM.ink2)
        case "upcoming": (VM.accentSoft, nil, VM.accent)
        default: (VM.sunken, nil, VM.muted)
        }
        return Circle()
            .fill(fill)
            .frame(width: size, height: size)
            .overlay {
                if let icon { Image(systemName: icon).font(.system(size: size * 0.42, weight: .bold)).foregroundStyle(ink) }
            }
    }

    private func weekday(_ iso: String) -> String {
        let p = DateFormatter()
        p.dateFormat = "yyyy-MM-dd"
        p.timeZone = Fmt.zone(home.timezone)
        guard let d = p.date(from: iso) else { return "" }
        let f = DateFormatter()
        f.locale = Fmt.locale(model.lang)
        f.timeZone = Fmt.zone(home.timezone)
        f.dateFormat = "EEEEE"
        return f.string(from: d)
    }
}

private struct HowDoingCard: View {
    @Environment(AppModel.self) private var model
    let how: HowDoing

    var body: some View {
        let b = Fmt.band(how.band, model)
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(model.t("How you're doing", "आपकी सेहत")).font(.title3.bold()).foregroundStyle(VM.ink)
                Spacer()
                Text(Fmt.day(how.at, tz: model.home?.timezone, model: model))
                    .font(.footnote)
                    .foregroundStyle(VM.muted)
            }
            StatusPill(label: b.label, icon: b.icon, ink: b.ink, soft: b.soft)
            Text(how.summary).font(.body).foregroundStyle(VM.ink2)
        }
        .card()
    }
}

private struct RemindersCard: View {
    @Environment(AppModel.self) private var model
    let home: PatientHome

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(model.t("Calls coming up", "आने वाली कॉल")).font(.title3.bold()).foregroundStyle(VM.ink)
            ForEach(home.reminders, id: \.self) { at in
                let time = Fmt.when(at, tz: home.timezone, model: model)
                HStack(spacing: 12) {
                    IconBadge(systemName: "phone.arrow.down.left", size: 38)
                    Text(model.t("VoiceMitra will call you at \(time)", "VoiceMitra आपको \(time) पर कॉल करेगा"))
                        .font(.body)
                        .foregroundStyle(VM.ink)
                }
            }
        }
        .card()
    }
}

/// Whether this phone can ring right now (the patient socket is up), and the "keep it open" reminder.
private struct ConnectionLine: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(model.socketConnected ? VM.good : VM.lineStrong)
                .frame(width: 10, height: 10)
                .padding(.top, 5)
            VStack(alignment: .leading, spacing: 2) {
                Text(model.socketConnected ? model.t("Ready for calls", "कॉल के लिए तैयार")
                                           : model.t("Connecting…", "जुड़ रहा है…"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(VM.ink2)
                Text(model.t("Keep VoiceMitra open to receive its calls.", "VoiceMitra की कॉल पाने के लिए ऐप खुला रखें।"))
                    .font(.footnote)
                    .foregroundStyle(VM.muted)
            }
        }
        .padding(.horizontal, 4)
        .accessibilityElement(children: .combine)
    }
}

/// A tappable coloured notice (errors, offline).
struct Notice: View {
    let text: String
    let icon: String
    let ink: Color
    let soft: Color
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: icon)
                Text(text).multilineTextAlignment(.leading)
                Spacer(minLength: 0)
            }
            .font(.body.weight(.semibold))
            .foregroundStyle(ink)
            .padding(16)
            .background(RoundedRectangle(cornerRadius: VM.radiusSmall, style: .continuous).fill(soft))
        }
        .buttonStyle(.plain)
    }
}
