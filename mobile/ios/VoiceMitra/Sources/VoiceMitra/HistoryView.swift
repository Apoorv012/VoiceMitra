import SwiftUI

/// The History tab (the web's /patients/[id]/history): one timeline of check-ins and the messages sent to the
/// family, newest first.
struct HistoryView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        TabPage(refresh: { await model.loadHistory() }) {
            PageTitle(text: model.t("Your check-ins", "आपकी बातचीत"))

            if let h = model.history {
                let items = Self.items(h)
                if items.isEmpty {
                    VStack(spacing: 12) {
                        IconBadge(systemName: "bubble.left.and.bubble.right.fill", size: 56)
                        Text(model.t("No check-ins yet.", "अभी तक कोई बातचीत नहीं हुई।"))
                            .font(.body).foregroundStyle(VM.muted)
                    }
                    .frame(maxWidth: .infinity)
                    .card(padding: 28)
                }
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(items.enumerated()), id: \.element.id) { i, item in
                        TimelineRow(item: item, tz: h.timezone ?? model.home?.timezone, isLast: i == items.count - 1)
                    }
                }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            }
        }
        .task { await model.loadHistory() }
    }

    enum Item: Identifiable {
        case checkin(Checkin)
        case alert(FamilyAlert)

        var at: Date {
            switch self {
            case .checkin(let c): c.at
            case .alert(let a): a.at
            }
        }

        var id: String {
            switch self {
            case .checkin(let c): "c-\(c.callId)"
            case .alert(let a): "a-\(a.id)"
            }
        }
    }

    static func items(_ h: PatientHistory) -> [Item] {
        (h.checkins.map(Item.checkin) + (h.alerts ?? []).map(Item.alert)).sorted { $0.at > $1.at }
    }
}

private struct TimelineRow: View {
    @Environment(AppModel.self) private var model
    let item: HistoryView.Item
    let tz: String?
    let isLast: Bool

    /// Dot colour, as on the web: a doctor or urgent -> crit; a remedy or a family alert -> warn; else good.
    private var tone: Color {
        switch item {
        case .alert: return VM.warnInk
        case .checkin(let c):
            if c.doctorConnected == true || c.patientStatus == "urgent" { return VM.crit }
            if c.patientStatus == "remedy" { return VM.warnInk }
            return VM.good
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                Circle()
                    .strokeBorder(tone, lineWidth: 3)
                    .background(Circle().fill(VM.surface))
                    .frame(width: 18, height: 18)
                    .padding(.top, 3)
                if !isLast {
                    Rectangle().fill(VM.lineStrong).frame(width: 2).frame(maxHeight: .infinity)
                }
            }
            .frame(width: 18)

            VStack(alignment: .leading, spacing: 8) {
                Text(Fmt.when(item.at, tz: tz, model: model))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(VM.muted)
                switch item {
                case .checkin(let c): checkinCard(c)
                case .alert(let a): alertCard(a)
                }
            }
            .padding(.bottom, isLast ? 0 : 20)
        }
        .accessibilityElement(children: .combine)
    }

    private func checkinCard(_ c: Checkin) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(model.t("Check-in call", "जाँच-बातचीत")).font(.headline).foregroundStyle(VM.ink)
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 6) { pills(c) }
                VStack(alignment: .leading, spacing: 6) { pills(c) }
            }
            if !c.symptoms.isEmpty {
                Text(model.t("You mentioned: \(c.symptoms.joined(separator: ", "))",
                             "आपने बताया: \(c.symptoms.joined(separator: ", "))"))
                    .font(.body)
                    .foregroundStyle(VM.ink2)
            }
            if let summary = c.summary, !summary.isEmpty {
                Text(summary).font(.subheadline).foregroundStyle(VM.muted)
            }
        }
        .card(padding: 18)
    }

    @ViewBuilder private func pills(_ c: Checkin) -> some View {
        if let s = Fmt.medicineStatus(c.medicineStatus, model) {
            StatusPill(label: s.label, icon: s.icon, ink: s.ink, soft: s.soft)
        }
        if c.escalated {
            StatusPill(label: c.doctorConnected == true ? model.t("A doctor joined this call", "इस कॉल में डॉक्टर जुड़े")
                                                        : model.t("A doctor was contacted", "डॉक्टर से संपर्क किया गया"),
                       icon: "stethoscope", ink: VM.critInk, soft: VM.critSoft)
        }
    }

    private func alertCard(_ a: FamilyAlert) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "heart.fill")
                .font(.title3)
                .foregroundStyle(VM.warnInk)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                Text(model.t("Family were told", "परिवार को बताया गया") + (a.caregiver.map { " · \($0)" } ?? ""))
                    .font(.headline)
                    .foregroundStyle(VM.warnInk)
                Text(a.message).font(.body).foregroundStyle(VM.ink)
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: VM.radiusSmall, style: .continuous).fill(VM.warnSoft))
    }
}
