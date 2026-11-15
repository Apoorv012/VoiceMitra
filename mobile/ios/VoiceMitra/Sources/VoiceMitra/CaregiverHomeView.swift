import SwiftUI

/// The family contact's home (API.md "Caregivers in the apps", C1): mirrors the website's `/caregivers/[id]`
/// page and its `cg_*` wording (web/src/lib/i18n.tsx) -- who they look after, the in-call banner, alerts with
/// Mark as seen, today's medicines, the week, how the patient is doing, Sign out. Read-only otherwise: no Talk
/// now, and this phone never rings. Live updates come over the caregiver socket while the app is open.
struct CaregiverHomeView: View {
    @Environment(AppModel.self) private var model
    @State private var confirmSignOut = false
    @State private var signingOut = false

    var body: some View {
        TabPage(refresh: { await model.loadCaregiverHome() }, bottomRoom: 32) {
            header
            if let home = model.caregiverHome {
                let first = Self.firstName(home.patient.name)
                if home.inCall {
                    Label(model.t("\(first) is talking to VoiceMitra right now.", "\(first) अभी VoiceMitra से बात कर रहे हैं।"),
                          systemImage: "phone.fill")
                        .font(.body.weight(.semibold))
                        .foregroundStyle(VM.accent)
                        .card(fill: VM.accentSoft, stroke: nil, padding: 16)
                        .accessibilityAddTraits(.updatesFrequently)
                }
                if let error = model.seenError {
                    Notice(text: error, icon: "exclamationmark.circle.fill", ink: VM.critInk, soft: VM.critSoft) {
                        model.seenError = nil
                    }
                }
                AlertsCard(home: home, patientFirst: first)
                TodayMedsCard(today: home.today, tz: home.timezone,
                              title: model.t("\(first)'s medicines today", "\(first) की आज की दवाइयाँ"),
                              footer: lastCheckin(home))
                WeekCard(week: home.week, adherence: home.adherence, tz: home.timezone)
                if let how = home.howDoing {
                    HowDoingCard(how: how, tz: home.timezone,
                                 title: model.t("How \(first) is doing", "\(first) की तबीयत"), showBand: false)
                }
                if model.caregiverError != nil {
                    Label(model.t("Couldn't refresh. Showing what we had.", "ताज़ा नहीं हो सका। पहले की जानकारी दिखा रहे हैं।"),
                          systemImage: "arrow.clockwise")
                        .font(.footnote)
                        .foregroundStyle(VM.muted)
                }
            } else if let error = model.caregiverError {
                Notice(text: error, icon: "wifi.exclamationmark", ink: VM.warnInk, soft: VM.warnSoft) {
                    Task { await model.loadCaregiverHome() }
                }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            }
            LiveLine()
            signOutButton
        }
        .confirmationDialog(model.t("Sign out of VoiceMitra on this phone?", "इस फ़ोन पर VoiceMitra से साइन आउट करें?"),
                            isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button(model.t("Sign out", "साइन आउट करें"), role: .destructive) {
                Task {
                    signingOut = true
                    await model.unpair()
                    signingOut = false
                }
            }
            Button(model.t("Cancel", "रद्द करें"), role: .cancel) {}
        }
    }

    private var header: some View {
        let patient = model.caregiverHome?.patient.name ?? model.pairing?.patientName ?? ""
        let me = Self.firstName(model.caregiverHome?.caregiver.name ?? model.pairing?.caregiverName ?? "")
        return VStack(alignment: .leading, spacing: 4) {
            Eyebrow(text: model.t("Looking after \(patient)", "\(patient) की देखभाल"))
            Text(me.isEmpty ? model.t("Hello", "नमस्ते") : model.t("Hello, \(me)", "नमस्ते, \(me)"))
                .font(.largeTitle.bold())
                .foregroundStyle(VM.ink)
                .accessibilityAddTraits(.isHeader)
        }
        .padding(.top, 6)
        .accessibilityElement(children: .combine)
    }

    private func lastCheckin(_ home: CaregiverHome) -> String {
        guard let last = home.lastCheckin else { return model.t("No check-ins yet", "अभी तक कोई बातचीत नहीं हुई") }
        let when = Fmt.when(last.at, tz: home.timezone, model: model)
        return model.t("Last check-in with VoiceMitra \(when)", "VoiceMitra से पिछली बातचीत \(when)")
    }

    private var signOutButton: some View {
        Button(role: .destructive) {
            confirmSignOut = true
        } label: {
            HStack(spacing: 10) {
                if signingOut { ProgressView() } else { Image(systemName: "rectangle.portrait.and.arrow.right") }
                Text(model.t("Sign out", "साइन आउट करें"))
            }
            .font(.title3.weight(.bold))
            .foregroundStyle(VM.critInk)
            .frame(maxWidth: .infinity, minHeight: 60)
            .background(Capsule().fill(VM.critSoft))
        }
        .buttonStyle(.plain)
        .disabled(signingOut)
        .padding(.top, 4)
    }

    static func firstName(_ name: String) -> String {
        name.split(separator: " ").first.map(String.init) ?? name
    }
}

/// Alerts: the new ones (Mark as seen, Mark all as seen), then the earlier ones folded away.
private struct AlertsCard: View {
    @Environment(AppModel.self) private var model
    @State private var showEarlier = false
    let home: CaregiverHome
    let patientFirst: String

    var body: some View {
        let fresh = home.alerts.filter { $0.seenAt == nil }
        let seen = home.alerts.filter { $0.seenAt != nil }
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text(model.t("Alerts", "अलर्ट")).font(.title3.bold()).foregroundStyle(VM.ink)
                    .accessibilityAddTraits(.isHeader)
                Spacer()
                if !fresh.isEmpty {
                    StatusPill(label: model.t("\(fresh.count) new", "नए: \(fresh.count)"), icon: "bell.fill",
                               ink: VM.critInk, soft: VM.critSoft)
                }
            }
            if home.alerts.isEmpty {
                Text(model.t("No alerts. You'll see one here if \(patientFirst) isn't feeling well or can't be reached.",
                             "कोई अलर्ट नहीं। अगर \(patientFirst) की तबीयत ठीक न हो या उनसे बात न हो सके, तो यहाँ दिखेगा।"))
                    .font(.body)
                    .foregroundStyle(VM.muted)
            } else if fresh.isEmpty {
                Text(model.t("No new alerts.", "कोई नया अलर्ट नहीं।")).font(.body).foregroundStyle(VM.muted)
            }

            ForEach(fresh) { alert in
                FreshAlert(alert: alert, tz: home.timezone)
            }

            if fresh.count > 1 {
                Button {
                    Task { await model.markSeen(nil) }
                } label: {
                    HStack(spacing: 8) {
                        if model.seenBusy == "all" { ProgressView() } else { Image(systemName: "checkmark.circle") }
                        Text(model.t("Mark all as seen", "सब देख लिए"))
                    }
                }
                .buttonStyle(SecondaryButtonStyle())
                .disabled(model.seenBusy != nil)
            }

            if !seen.isEmpty {
                DisclosureGroup(isExpanded: $showEarlier) {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach(seen) { alert in
                            EarlierAlert(alert: alert, tz: home.timezone)
                        }
                    }
                    .padding(.top, 10)
                } label: {
                    Text("\(model.t("Earlier", "पहले के")) (\(seen.count))")
                        .font(.body.weight(.semibold))
                        .foregroundStyle(VM.ink2)
                }
                .tint(VM.ink2)
            }
        }
        .card()
    }
}

@MainActor
private func alertLabel(_ alert: CaregiverAlert, _ model: AppModel) -> String {
    if alert.urgent { return model.t("Urgent", "ज़रूरी") }
    if alert.trigger == "unreachable" { return model.t("Couldn't be reached", "बात नहीं हो सकी") }
    return model.t("Not feeling well", "तबीयत ठीक नहीं")
}

/// A new alert: on red (urgent) or amber, with its own Mark as seen.
private struct FreshAlert: View {
    @Environment(AppModel.self) private var model
    let alert: CaregiverAlert
    let tz: String

    var body: some View {
        let ink = alert.urgent ? VM.critInk : VM.warnInk
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: alert.urgent ? "exclamationmark.triangle.fill" : "exclamationmark.circle.fill")
                    .font(.title3)
                    .foregroundStyle(ink)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(alertLabel(alert, model)).font(.headline).foregroundStyle(ink)
                    Text(Fmt.when(alert.at, tz: tz, model: model)).font(.subheadline.weight(.medium)).foregroundStyle(VM.ink2)
                    Text(alert.message).font(.body).foregroundStyle(VM.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .accessibilityElement(children: .combine)
            Button {
                Task { await model.markSeen(alert.id) }
            } label: {
                HStack(spacing: 8) {
                    if model.seenBusy == alert.id { ProgressView().tint(VM.onBtn) } else { Image(systemName: "checkmark") }
                    Text(model.t("Mark as seen", "देख लिया"))
                }
                .font(.body.weight(.bold))
                .foregroundStyle(VM.onBtn)
                .frame(maxWidth: .infinity, minHeight: 52)
                .background(Capsule().fill(VM.btn.opacity(model.seenBusy == nil ? 1 : 0.35)))
            }
            .buttonStyle(.plain)
            .disabled(model.seenBusy != nil)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: VM.radiusSmall, style: .continuous)
            .fill(alert.urgent ? VM.critSoft : VM.warnSoft))
    }
}

/// A seen alert: label, when, the message, and when it was seen.
private struct EarlierAlert: View {
    @Environment(AppModel.self) private var model
    let alert: CaregiverAlert
    let tz: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            (Text(alertLabel(alert, model)).font(.subheadline.bold()).foregroundStyle(VM.ink)
             + Text(" · \(Fmt.when(alert.at, tz: tz, model: model))").font(.subheadline).foregroundStyle(VM.muted))
            Text(alert.message).font(.subheadline).foregroundStyle(VM.ink2)
                .fixedSize(horizontal: false, vertical: true)
            if let seenAt = alert.seenAt {
                let when = Fmt.when(seenAt, tz: tz, model: model)
                Text(model.t("Seen \(when)", "देखा गया: \(when)")).font(.footnote).foregroundStyle(VM.muted)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Whether live updates are on (the caregiver socket), and that the iPhone shows alerts only while open.
private struct LiveLine: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(model.socketConnected ? VM.good : VM.lineStrong)
                .frame(width: 10, height: 10)
                .padding(.top, 5)
            VStack(alignment: .leading, spacing: 2) {
                Text(model.socketConnected ? model.t("Up to date", "ताज़ा जानकारी")
                                           : model.t("Connecting…", "जुड़ रहा है…"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(VM.ink2)
                Text(model.t("New alerts show up here while VoiceMitra is open. The iPhone can't notify you when it's closed.",
                             "VoiceMitra खुला होने पर नए अलर्ट यहाँ दिखते हैं। ऐप बंद हो तो iPhone सूचना नहीं दे सकता।"))
                    .font(.footnote)
                    .foregroundStyle(VM.muted)
            }
        }
        .padding(.horizontal, 4)
        .accessibilityElement(children: .combine)
    }
}
