import SwiftUI

/// The Me tab: who's signed in, family contact, language, server, and Sign out.
struct MeView: View {
    @Environment(AppModel.self) private var model
    @State private var confirmSignOut = false
    @State private var showServer = false
    @State private var showAdvanced = false
    @State private var signingOut = false

    var body: some View {
        TabPage(refresh: { await model.loadHome() }) {
            profile

            // The language switch is in the header on every tab, so there's no Language row here.
            if let cg = model.home?.caregiver { CaregiverCard(caregiver: cg) }

            AllergiesCard(allergies: model.home?.allergies ?? [])

            // This phone
            HStack(alignment: .top, spacing: 14) {
                IconBadge(systemName: "iphone.radiowaves.left.and.right")
                VStack(alignment: .leading, spacing: 4) {
                    Text(model.t("This iPhone", "यह iPhone")).font(.headline).foregroundStyle(VM.ink)
                    Text(model.t("VoiceMitra rings here while the app is open. Keep it open when you expect a call.",
                                 "ऐप खुला होने पर VoiceMitra की कॉल यहाँ आती है। कॉल की उम्मीद हो तो ऐप खुला रखें।"))
                        .font(.body)
                        .foregroundStyle(VM.ink2)
                }
            }
            .card()

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

            // Setup details patients don't need: collapsed, at the very bottom.
            DisclosureGroup(isExpanded: $showAdvanced) {
                Button { showServer = true } label: {
                    row(icon: "server.rack", title: model.t("Server", "सर्वर")) {
                        HStack(spacing: 6) {
                            Text(URL(string: model.server)?.host ?? model.server)
                                .font(.subheadline)
                                .foregroundStyle(VM.muted)
                                .lineLimit(1)
                            Image(systemName: "chevron.right").font(.footnote.bold()).foregroundStyle(VM.muted)
                        }
                    }
                }
                .buttonStyle(.plain)
                .padding(.top, 6)
            } label: {
                Text(model.t("Advanced", "एडवांस्ड"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(VM.muted)
            }
            .tint(VM.muted)
            .padding(.horizontal, 6)

            Text(appVersion)
                .font(.caption)
                .foregroundStyle(VM.muted)
                .frame(maxWidth: .infinity)
        }
        .confirmationDialog(model.t("Sign out of VoiceMitra? Calls won't ring on this phone until you sign in again.",
                                    "VoiceMitra से साइन आउट करें? दोबारा साइन इन करने तक इस फ़ोन पर कॉल नहीं आएँगी।"),
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
        .sheet(isPresented: $showServer) { ServerSettingsSheet() }
    }

    private var profile: some View {
        let name = model.home?.patient.name ?? model.pairing?.patientName ?? ""
        let initials = name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined()
        return HStack(spacing: 16) {
            Circle()
                .fill(VM.sage)
                .frame(width: 76, height: 76)
                .overlay { Text(initials.uppercased()).font(.title.bold()).foregroundStyle(VM.accent) }
            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.title.bold())
                    .foregroundStyle(VM.ink)
                if let age = model.home?.patient.age {
                    Text(model.t("\(age) years old", "\(age) वर्ष")).font(.body).foregroundStyle(VM.muted)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.top, 6)
        .accessibilityElement(children: .combine)
    }

    private func row<Trailing: View>(icon: String, title: String, @ViewBuilder trailing: () -> Trailing) -> some View {
        HStack(spacing: 14) {
            IconBadge(systemName: icon, size: 40)
            Text(title).font(.headline).foregroundStyle(VM.ink)
            Spacer(minLength: 8)
            trailing()
        }
        .padding(.horizontal, 12)
        .frame(minHeight: 64)
        .contentShape(Rectangle())
    }

    private var appVersion: String {
        let v = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
        return "VoiceMitra \(v)"
    }
}

private struct CaregiverCard: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openURL) private var openURL
    let caregiver: CaregiverView

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 14) {
                IconBadge(systemName: "person.2.fill")
                VStack(alignment: .leading, spacing: 2) {
                    Eyebrow(text: model.t("Family contact", "परिवार का संपर्क"))
                    Text(caregiver.name).font(.title3.bold()).foregroundStyle(VM.ink)
                    Text(caregiver.relation).font(.body).foregroundStyle(VM.ink2)
                }
                Spacer(minLength: 0)
            }
            if let url = URL(string: "tel:\(caregiver.phoneNumber.filter { $0.isNumber || $0 == "+" })") {
                Button {
                    openURL(url)
                } label: {
                    Label(model.t("Call \(caregiver.name.split(separator: " ").first.map(String.init) ?? caregiver.name)",
                                  "\(caregiver.name.split(separator: " ").first.map(String.init) ?? caregiver.name) को कॉल करें"),
                          systemImage: "phone.fill")
                }
                .buttonStyle(SecondaryButtonStyle(tint: VM.accent))
            }
        }
        .card()
    }
}

/// Server address (dev / pilot). Default: the tunnel.
struct ServerSettingsSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var server = ""

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField(Prefs.defaultServer, text: $server)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    if API(server: server) == nil {
                        Text(model.t("Enter an address starting with https://", "https:// से शुरू होने वाला पता लिखें"))
                            .foregroundStyle(VM.critInk)
                    }
                    Button(model.t("Use the default", "डिफ़ॉल्ट इस्तेमाल करें")) { server = Prefs.defaultServer }
                } header: {
                    Text(model.t("Server address", "सर्वर का पता"))
                } footer: {
                    Text(model.t("Only change this if you were asked to.", "इसे तभी बदलें जब आपसे कहा गया हो।"))
                }
            }
            .navigationTitle(model.t("Server", "सर्वर"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(model.t("Cancel", "रद्द करें")) { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(model.t("Save", "सेव करें")) {
                        if API(server: server) != nil, server != model.server { model.server = server }
                        dismiss()
                    }
                    .disabled(API(server: server) == nil)
                }
            }
            .onAppear { server = model.server }
        }
        .presentationDetents([.medium])
    }
}
