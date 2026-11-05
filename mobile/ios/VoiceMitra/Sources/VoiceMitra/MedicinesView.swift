import SwiftUI

/// The Medicines tab (the web's /patients/[id]/medicines): allergies, current and finished medicines with
/// their schedule and how many were taken this week.
struct MedicinesView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        TabPage(refresh: { await model.loadMedicines() }) {
            PageTitle(text: model.t("Your medicines", "आपकी दवाइयाँ"))

            if let m = model.medicines {
                AllergiesCard(allergies: m.allergies)
                let current = m.medicines.filter(\.active)
                let past = m.medicines.filter { !$0.active }
                if m.medicines.isEmpty {
                    Text(model.t("No medicines on your list yet.", "आपकी सूची में अभी कोई दवा नहीं है।"))
                        .font(.body).foregroundStyle(VM.muted)
                        .card()
                }
                if !current.isEmpty {
                    Eyebrow(text: model.t("Current", "अभी की")).padding(.top, 4)
                    ForEach(current) { MedicineCard(medicine: $0) }
                }
                if !past.isEmpty {
                    Eyebrow(text: model.t("Finished", "पूरी हो चुकीं")).padding(.top, 4)
                    ForEach(past) { MedicineCard(medicine: $0).opacity(0.7) }
                }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            }
        }
        .task { await model.loadMedicines() }
    }
}

struct AllergiesCard: View {
    @Environment(AppModel.self) private var model
    let allergies: [String]

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            IconBadge(systemName: "shield.fill", tint: allergies.isEmpty ? VM.accent : VM.warnInk,
                      fill: allergies.isEmpty ? VM.accentSoft : VM.warnSoft)
            VStack(alignment: .leading, spacing: 4) {
                Text(model.t("Allergies", "एलर्जी")).font(.headline).foregroundStyle(VM.ink)
                Text(allergies.isEmpty ? model.t("No known allergies", "कोई ज्ञात एलर्जी नहीं") : allergies.joined(separator: ", "))
                    .font(.body)
                    .foregroundStyle(VM.ink2)
            }
            Spacer(minLength: 0)
        }
        .card(fill: VM.sunken, stroke: nil)
    }
}

private struct MedicineCard: View {
    @Environment(AppModel.self) private var model
    let medicine: MedicineView

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 14) {
                IconBadge(systemName: "pills.fill")
                VStack(alignment: .leading, spacing: 2) {
                    Text(medicine.name).font(.title3.bold()).foregroundStyle(VM.ink)
                    Text(medicine.dose).font(.body).foregroundStyle(VM.ink2)
                }
                Spacer(minLength: 0)
            }
            Label(Fmt.schedule(medicine, model: model), systemImage: "clock")
                .font(.body.weight(.medium))
                .foregroundStyle(VM.ink)
            if let left = medicine.daysLeft {
                Label(left <= 0 ? model.t("Last day today", "आज आख़िरी दिन है")
                                : model.t("\(left) days left", "\(left) दिन बाकी"),
                      systemImage: "calendar")
                    .font(.subheadline)
                    .foregroundStyle(left <= 2 ? VM.warnInk : VM.muted)
            }
            if medicine.known > 0 {
                VStack(alignment: .leading, spacing: 6) {
                    ProgressView(value: Double(medicine.taken), total: Double(max(medicine.known, 1)))
                        .tint(VM.good)
                        .scaleEffect(x: 1, y: 1.6, anchor: .center)
                    Text(model.t("\(medicine.taken) of \(medicine.known) taken this week",
                                 "इस हफ़्ते \(medicine.known) में से \(medicine.taken) ली"))
                        .font(.footnote)
                        .foregroundStyle(VM.muted)
                }
            }
        }
        .card()
        .accessibilityElement(children: .combine)
    }
}
