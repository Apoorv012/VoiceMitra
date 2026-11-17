import SwiftUI

/// The Medicines tab (the web's /patients/[id]/medicines). Two kinds: the doctor's prescription (entered by the
/// clinic, read-only here) and the patient's own medicines, which they add, change and remove (API.md "Own
/// medicines"). Plus allergies, and finished medicines.
struct MedicinesView: View {
    @Environment(AppModel.self) private var model
    @State private var sheet: SheetMode?
    @State private var confirming: MedicineView?
    @State private var removing = false
    @State private var removeError = false
    @State private var notice: String?

    var body: some View {
        TabPage(refresh: { await model.loadMedicines() }) {
            PageTitle(text: model.t("Your medicines", "आपकी दवाइयाँ"))

            if let m = model.medicines {
                AllergiesCard(allergies: m.allergies)

                if let notice {
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "checkmark.circle.fill").foregroundStyle(VM.goodInk)
                        Text(notice).font(.body).foregroundStyle(VM.ink).frame(maxWidth: .infinity, alignment: .leading)
                        Button { self.notice = nil } label: { Image(systemName: "xmark").foregroundStyle(VM.ink2) }
                            .accessibilityLabel(model.t("Close", "बंद करें"))
                    }
                    .card(fill: VM.goodSoft, stroke: nil)
                }
                if removeError {
                    Text(model.t("Couldn't remove it. Please try again.", "हटाया नहीं जा सका। फिर से कोशिश करें।"))
                        .font(.body).foregroundStyle(VM.critInk)
                        .card(fill: VM.critSoft, stroke: nil)
                }

                let prescribed = m.medicines.filter { $0.active && !$0.isOwn }
                let own = m.medicines.filter { $0.active && $0.isOwn }
                let past = m.medicines.filter { !$0.active }

                Eyebrow(text: model.t("From your doctor", "डॉक्टर की लिखी दवाइयाँ")).padding(.top, 4)
                Text(model.t("Your clinic added these from your prescription. Only they can change them.",
                             "ये आपके क्लिनिक ने आपके पर्चे से जोड़ी हैं। इन्हें सिर्फ़ वही बदल सकते हैं।"))
                    .font(.subheadline).foregroundStyle(VM.ink2)
                if prescribed.isEmpty {
                    Text(model.t("Nothing from your doctor yet.", "डॉक्टर की कोई दवा अभी नहीं जुड़ी है।"))
                        .font(.body).foregroundStyle(VM.muted)
                        .card()
                }
                ForEach(prescribed) { MedicineCard(medicine: $0) }

                Eyebrow(text: model.t("Your own medicines", "आपकी अपनी दवाइयाँ")).padding(.top, 8)
                Text(model.t("Anything you take on your own. You can add, change or remove these, and we remind you about them too.",
                             "जो दवाइयाँ आप अपने से लेते हैं। इन्हें आप जोड़, बदल या हटा सकते हैं, और हम इनकी भी याद दिलाते हैं।"))
                    .font(.subheadline).foregroundStyle(VM.ink2)
                if own.isEmpty {
                    Text(model.t("You haven't added any.", "आपने अभी कोई दवा नहीं जोड़ी है।"))
                        .font(.body).foregroundStyle(VM.muted)
                }
                ForEach(own) { med in
                    MedicineCard(medicine: med, onEdit: { start(.edit(med)) }, onRemove: { removeError = false; confirming = med })
                }
                Button { start(.add) } label: {
                    Label(model.t("Add a medicine", "दवा जोड़ें"), systemImage: "plus")
                }
                .buttonStyle(PrimaryButtonStyle())

                if !past.isEmpty {
                    Eyebrow(text: model.t("Finished", "पूरी हो चुकीं")).padding(.top, 8)
                    ForEach(past) { med in
                        if med.isOwn {
                            MedicineCard(medicine: med, onEdit: { start(.edit(med)) },
                                         onRemove: { removeError = false; confirming = med })
                                .opacity(0.75)
                        } else {
                            MedicineCard(medicine: med).opacity(0.7)
                        }
                    }
                }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            }
        }
        .task { await model.loadMedicines() }
        .sheet(item: $sheet) { mode in
            OwnMedicineSheet(editing: mode.editing) { name in
                notice = model.t("\(name) is saved.", "\(name) सेव हो गई।")
            }
        }
        .confirmationDialog(
            confirming.map { model.t("Remove \($0.name)?", "\($0.name) हटाएँ?") } ?? "",
            isPresented: Binding(get: { confirming != nil }, set: { if !$0 && !removing { confirming = nil } }),
            titleVisibility: .visible,
            presenting: confirming
        ) { med in
            Button(model.t("Yes, remove", "हाँ, हटाएँ"), role: .destructive) { remove(med) }
            Button(model.t("Keep it", "रहने दें"), role: .cancel) { confirming = nil }
        }
    }

    private func start(_ mode: SheetMode) {
        notice = nil
        removeError = false
        sheet = mode
    }

    private func remove(_ med: MedicineView) {
        removing = true
        Task {
            defer { removing = false; confirming = nil }
            do {
                let outcome = try await model.removeMedicine(med)
                notice = outcome == "stopped"
                    ? model.t("\(med.name) is stopped. It stays under Finished.", "\(med.name) बंद कर दी गई। यह \"पूरी हो चुकीं\" में दिखेगी।")
                    : model.t("\(med.name) is removed.", "\(med.name) हटा दी गई।")
            } catch {
                removeError = true
            }
        }
    }
}

private enum SheetMode: Identifiable {
    case add
    case edit(MedicineView)

    var id: String {
        switch self {
        case .add: "add"
        case .edit(let m): m.dosageId
        }
    }

    var editing: MedicineView? {
        if case .edit(let m) = self { return m }
        return nil
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
    var onEdit: (() -> Void)? = nil
    var onRemove: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 14) {
                    IconBadge(systemName: "pills.fill")
                    VStack(alignment: .leading, spacing: 2) {
                        Text(medicine.name).font(.title3.bold()).foregroundStyle(VM.ink)
                        Text(medicine.dose).font(.body).foregroundStyle(VM.ink2)
                    }
                    Spacer(minLength: 0)
                }
                if !medicine.active && medicine.isOwn {
                    Text(model.t("Added by you", "आपने जोड़ी"))
                        .font(.footnote.weight(.semibold)).foregroundStyle(VM.ink2)
                        .padding(.horizontal, 10).padding(.vertical, 4)
                        .background(Capsule().fill(VM.neutralSoft))
                }
                Label(Fmt.schedule(medicine, model: model), systemImage: "clock")
                    .font(.body.weight(.medium))
                    .foregroundStyle(VM.ink)
                if medicine.active, let left = medicine.daysLeft {
                    Label(left <= 0 ? model.t("Last day today", "आज आख़िरी दिन है")
                                    : model.t("\(left) days left", "\(left) दिन बाकी"),
                          systemImage: "calendar")
                        .font(.subheadline)
                        .foregroundStyle(left <= 2 ? VM.warnInk : VM.muted)
                }
                if medicine.active && medicine.known > 0 {
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
            .accessibilityElement(children: .combine)

            if let onEdit, let onRemove {
                HStack(spacing: 10) {
                    Button(action: onEdit) { Label(model.t("Change", "बदलें"), systemImage: "pencil") }
                        .buttonStyle(SecondaryButtonStyle())
                    Button(action: onRemove) { Label(model.t("Remove", "हटाएँ"), systemImage: "trash") }
                        .buttonStyle(SecondaryButtonStyle(tint: VM.critInk))
                }
            }
        }
        .card()
    }
}

// MARK: - add / change one of the patient's own medicines

private struct TimeRow: Identifiable {
    let id = UUID()
    var date: Date
}

struct OwnMedicineSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let editing: MedicineView?
    let onSaved: (String) -> Void

    @State private var name = ""
    @State private var dose = ""
    @State private var times: [TimeRow] = []
    @State private var often = "fixed_times"
    @State private var every = 2
    @State private var from = Date()
    @State private var hasEnd = false
    @State private var until = Date()
    @State private var busy = false
    @State private var problem: String?
    @State private var loaded = false

    private static let maxTimes = 6

    var body: some View {
        NavigationStack {
            Form {
                Section(model.t("Medicine name", "दवा का नाम")) {
                    TextField(model.t("Medicine name", "दवा का नाम"), text: $name)
                        .font(.title3)
                        .textInputAutocapitalization(.words)
                }
                Section(model.t("How much", "कितनी")) {
                    TextField(model.t("e.g. 1 tablet", "जैसे 1 गोली"), text: $dose)
                        .font(.title3)
                }
                Section(model.t("What time", "किस समय")) {
                    ForEach($times) { $row in
                        HStack {
                            DatePicker(model.t("Time", "समय"), selection: $row.date, displayedComponents: .hourAndMinute)
                                .font(.title3)
                            if times.count > 1 {
                                Button { times.removeAll { $0.id == row.id } } label: {
                                    Image(systemName: "minus.circle.fill").font(.title2).foregroundStyle(VM.critInk)
                                }
                                .buttonStyle(.plain)
                                .accessibilityLabel(model.t("Remove this time", "यह समय हटाएँ"))
                            }
                        }
                    }
                    if times.count < Self.maxTimes {
                        Button {
                            times.append(TimeRow(date: Self.date(hhmm: "20:00")))
                        } label: {
                            Label(model.t("Add another time", "एक और समय"), systemImage: "plus.circle.fill")
                        }
                    }
                }
                Section {
                    Picker(model.t("How often", "कितनी बार"), selection: $often) {
                        Text(model.t("Every day", "रोज़")).tag("fixed_times")
                        Text(model.t("Once a week", "हफ़्ते में एक बार")).tag("weekly")
                        Text(model.t("Every few days", "कुछ दिनों में एक बार")).tag("every_x_day")
                    }
                    .pickerStyle(.inline)
                    .labelsHidden()
                    if often == "every_x_day" {
                        Stepper(model.t("Every \(every) days", "हर \(every) दिन"), value: $every, in: 2...90)
                            .font(.title3)
                    }
                } header: {
                    Text(model.t("How often", "कितनी बार"))
                } footer: {
                    if often == "weekly" {
                        Text(model.t("On the same weekday as the start date.", "शुरू की तारीख़ वाले दिन, हर हफ़्ते।"))
                    }
                }
                Section {
                    DatePicker(model.t("Starting", "कब से"), selection: $from, displayedComponents: .date)
                    Toggle(model.t("Until (if you know)", "कब तक (अगर पता हो)"), isOn: $hasEnd)
                    if hasEnd {
                        DatePicker(model.t("Until", "कब तक"), selection: $until, in: from..., displayedComponents: .date)
                    }
                }
                if let problem {
                    Section { Text(problem).foregroundStyle(VM.critInk) }
                }
            }
            .environment(\.locale, Fmt.locale(model.lang))
            .navigationTitle(editing.map { model.t("Change \($0.name)", "\($0.name) बदलें") }
                             ?? model.t("Add your own medicine", "अपनी दवा जोड़ें"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(model.t("Cancel", "रद्द करें")) { dismiss() }.disabled(busy)
                }
                ToolbarItem(placement: .confirmationAction) {
                    if busy { ProgressView() } else {
                        Button(model.t("Save", "सेव करें")) { save() }.bold()
                    }
                }
            }
            .interactiveDismissDisabled(busy)
            .onAppear(perform: fill)
        }
    }

    private func fill() {
        guard !loaded else { return }
        loaded = true
        guard let m = editing else {
            times = [TimeRow(date: Self.date(hhmm: "08:00"))]
            return
        }
        name = m.name
        dose = m.dose
        times = (m.times.isEmpty ? ["08:00"] : m.times).map { TimeRow(date: Self.date(hhmm: $0)) }
        often = ["weekly", "every_x_day"].contains(m.frequency) ? m.frequency : "fixed_times"
        every = m.intervalDays ?? 2
        if let f = m.fromDate.flatMap(Self.day(from:)) { from = f }
        if let u = m.toDate.flatMap(Self.day(from:)) { until = u; hasEnd = true }
    }

    private func save() {
        let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanDose = dose.trimmingCharacters(in: .whitespacesAndNewlines)
        let hhmm = Array(Set(times.map { Self.hhmm($0.date) })).sorted()
        if cleanName.isEmpty { problem = model.t("Write the medicine's name.", "दवा का नाम लिखें।"); return }
        if cleanDose.isEmpty { problem = model.t("Write how much you take.", "कितनी लेते हैं, यह लिखें।"); return }
        if hasEnd && Self.iso(until) < Self.iso(from) {
            problem = model.t("The end date is before the start date.", "ख़त्म होने की तारीख़ शुरू की तारीख़ से पहले है।"); return
        }
        let body = OwnMedicineBody(
            medicineName: String(cleanName.prefix(80)), dosage: String(cleanDose.prefix(80)), frequency: often, times: hhmm,
            intervalDays: often == "every_x_day" ? every : nil, fromDate: Self.iso(from), toDate: hasEnd ? Self.iso(until) : nil)
        busy = true
        problem = nil
        Task {
            defer { busy = false }
            do {
                try await model.saveOwnMedicine(body, editing: editing)
                onSaved(body.medicineName)
                dismiss()
            } catch {
                problem = model.t("Couldn't save. Please try again.", "सेव नहीं हो पाया। फिर से कोशिश करें।")
            }
        }
    }

    // Times and dates as the API writes them, in the phone's own calendar (the patient's local time).
    private static var calendar: Calendar { Calendar(identifier: .gregorian) }

    private static func date(hhmm: String) -> Date {
        let p = hhmm.split(separator: ":").compactMap { Int($0) }
        return calendar.date(bySettingHour: p.first ?? 8, minute: p.count > 1 ? p[1] : 0, second: 0, of: Date()) ?? Date()
    }

    private static func hhmm(_ d: Date) -> String {
        let c = calendar.dateComponents([.hour, .minute], from: d)
        return String(format: "%02d:%02d", c.hour ?? 0, c.minute ?? 0)
    }

    private static func iso(_ d: Date) -> String {
        let c = calendar.dateComponents([.year, .month, .day], from: d)
        return String(format: "%04d-%02d-%02d", c.year ?? 2000, c.month ?? 1, c.day ?? 1)
    }

    private static func day(from s: String) -> Date? {
        let p = s.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3 else { return nil }
        return calendar.date(from: DateComponents(year: p[0], month: p[1], day: p[2], hour: 12))
    }
}
