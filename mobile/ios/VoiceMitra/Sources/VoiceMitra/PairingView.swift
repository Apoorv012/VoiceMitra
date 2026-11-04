import SwiftUI

/// First screen: sign in with username + password (POST /api/auth/login). "Use a code instead" switches to
/// the 6-digit pairing code from the web (patient's Me tab -> "Connect a phone"). Both store the same pairing.
struct PairingView: View {
    @Environment(AppModel.self) private var model
    @State private var useCode = false
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if useCode {
                        CodeForm()
                    } else {
                        PasswordForm()
                    }
                    Button {
                        useCode.toggle()
                    } label: {
                        Text(useCode ? model.t("Sign in with username and password instead", "इसकी जगह यूज़रनेम और पासवर्ड से साइन इन करें")
                                     : model.t("Use a code instead", "इसकी जगह कोड इस्तेमाल करें"))
                            .font(.title3.weight(.semibold))
                            .underline()
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.tint)

                    #if DEV_PICKER
                    DevPicker()
                    #endif
                }
                .padding(20)
            }
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
}

@MainActor
private func offlineMessage(_ model: AppModel) -> String {
    model.t("Couldn't reach VoiceMitra. Check the internet and the server address (gear icon).",
            "VoiceMitra से संपर्क नहीं हो सका। इंटरनेट और सर्वर का पता (गियर बटन) जाँचें।")
}

private struct ErrorLine: View {
    let text: String?

    var body: some View {
        if let text {
            Label(text, systemImage: "exclamationmark.triangle.fill")
                .font(.body.weight(.semibold))
                .foregroundStyle(.red)
        }
    }
}

private struct SubmitButton: View {
    @Environment(AppModel.self) private var model
    let title: String
    let busy: Bool
    let enabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                if busy { ProgressView().tint(.white) }
                Text(busy ? model.t("Signing in…", "साइन इन हो रहा है…") : title)
            }
            .font(.title2.bold())
            .frame(maxWidth: .infinity, minHeight: 64)
        }
        .buttonStyle(.borderedProminent)
        .disabled(!enabled || busy)
    }
}

/// Large, high-contrast field (elderly users; scales with Dynamic Type).
private struct BigField: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(.title2)
            .padding(.horizontal, 14)
            .frame(minHeight: 60)
            .background(RoundedRectangle(cornerRadius: 14).stroke(.primary, lineWidth: 2))
    }
}

private struct PasswordForm: View {
    @Environment(AppModel.self) private var model
    @State private var username = ""
    @State private var password = ""
    @State private var showPassword = false
    @State private var busy = false
    @State private var error: String?
    @FocusState private var field: Field?

    enum Field { case username, password }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(model.t("Sign in", "साइन इन करें")).font(.largeTitle.bold())

            VStack(alignment: .leading, spacing: 8) {
                Text(model.t("Username", "यूज़रनेम")).font(.title3.weight(.semibold))
                TextField("", text: $username)
                    .textContentType(.username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.next)
                    .focused($field, equals: .username)
                    .onSubmit { field = .password }
                    .modifier(BigField())
            }

            VStack(alignment: .leading, spacing: 8) {
                Text(model.t("Password", "पासवर्ड")).font(.title3.weight(.semibold))
                HStack(spacing: 8) {
                    Group {
                        if showPassword {
                            TextField("", text: $password)
                        } else {
                            SecureField("", text: $password)
                        }
                    }
                    .textContentType(.password)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.go)
                    .focused($field, equals: .password)
                    .onSubmit { if canSubmit { Task { await submit() } } }

                    Button {
                        showPassword.toggle()
                    } label: {
                        Image(systemName: showPassword ? "eye.slash" : "eye")
                            .font(.title2)
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(showPassword ? model.t("Hide password", "पासवर्ड छिपाएँ")
                                                     : model.t("Show password", "पासवर्ड दिखाएँ"))
                }
                .modifier(BigField())
            }

            ErrorLine(text: error)
            SubmitButton(title: model.t("Sign in", "साइन इन करें"), busy: busy, enabled: canSubmit) {
                Task { await submit() }
            }
        }
        .onAppear { field = .username }
    }

    private var canSubmit: Bool { !username.trimmingCharacters(in: .whitespaces).isEmpty && !password.isEmpty }

    private func submit() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            try await model.login(username: username, password: password)
        } catch let e as APIError where e.status == 401 {
            error = model.t("Wrong username or password. Please try again.", "यूज़रनेम या पासवर्ड गलत है। कृपया फिर कोशिश करें।")
        } catch let e as APIError where e.status == 429 {
            error = model.t("Too many tries. Please try again later.", "बहुत बार कोशिश हो गई। कृपया थोड़ी देर बाद फिर कोशिश करें।")
        } catch {
            self.error = offlineMessage(model)
        }
    }
}

private struct CodeForm: View {
    @Environment(AppModel.self) private var model
    @State private var code = ""
    @State private var busy = false
    @State private var error: String?
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(model.t("Connect with a code", "कोड से जोड़ें")).font(.largeTitle.bold())
            Text(model.t("On the VoiceMitra website, open the patient's \"Me\" tab and tap \"Connect a phone\". Type the 6-digit code here.",
                         "VoiceMitra वेबसाइट पर मरीज़ का \"मैं\" टैब खोलें और \"फ़ोन जोड़ें\" दबाएँ। 6 अंकों का कोड यहाँ लिखें।"))
                .font(.title3)

            TextField("123456", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .font(.system(size: 44, weight: .bold, design: .monospaced))
                .multilineTextAlignment(.center)
                .padding(.vertical, 12)
                .background(RoundedRectangle(cornerRadius: 14).stroke(.primary, lineWidth: 2))
                .focused($focused)
                .onChange(of: code) { _, new in
                    let digits = String(new.filter(\.isNumber).prefix(6))
                    if digits != new { code = digits }
                }

            ErrorLine(text: error)
            SubmitButton(title: model.t("Connect", "जोड़ें"), busy: busy, enabled: code.count == 6) {
                Task { await submit() }
            }
        }
        .onAppear { focused = true }
    }

    private func submit() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            try await model.pair(code: code)
        } catch let e as APIError where e.status == 400 {
            error = model.t("That code is wrong or has expired. Get a new code and try again.",
                            "यह कोड गलत है या उसका समय निकल गया। नया कोड लेकर फिर कोशिश करें।")
        } catch let e as APIError where e.status == 429 {
            error = model.t("Too many wrong codes. Please try again later.",
                            "बहुत बार गलत कोड डाला गया। कृपया थोड़ी देर बाद फिर कोशिश करें।")
        } catch {
            self.error = offlineMessage(model)
        }
    }
}

#if DEV_PICKER
/// Debug builds only: act as any patient from GET /api/app/people, without pairing.
private struct DevPicker: View {
    @Environment(AppModel.self) private var model
    @State private var people: [Person]?
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider().padding(.vertical, 8)
            Text("Developer: pick a patient").font(.headline)
            if let people {
                ForEach(people) { p in
                    Button { model.pickDev(p) } label: {
                        Text(p.name).frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .buttonStyle(.bordered)
                }
            } else if let error {
                Text(error).foregroundStyle(.red)
            } else {
                ProgressView()
            }
        }
        .task(id: model.server) {
            do {
                people = try await model.api?.people().patients ?? []
            } catch {
                self.error = "\(error.localizedDescription)"
            }
        }
    }
}
#endif

struct LanguageToggle: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        Picker(model.t("Language", "भाषा"), selection: $model.lang) {
            Text("English").tag(Lang.en)
            Text("हिंदी").tag(Lang.hi)
        }
        .pickerStyle(.segmented)
        .frame(width: 170)
    }
}

struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var server = ""
    @State private var confirmSignOut = false

    var body: some View {
        NavigationStack {
            Form {
                Section(model.t("Server", "सर्वर")) {
                    TextField(Prefs.defaultServer, text: $server)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    if API(server: server) == nil {
                        Text(model.t("Enter an address starting with https://", "https:// से शुरू होने वाला पता लिखें"))
                            .foregroundStyle(.red)
                    }
                    Button(model.t("Use the default", "डिफ़ॉल्ट इस्तेमाल करें")) { server = Prefs.defaultServer }
                }
                if let p = model.pairing {
                    Section(model.t("This phone", "यह फ़ोन")) {
                        LabeledContent(model.t("Patient", "मरीज़"), value: p.patientName)
                        Button(model.t("Sign out of this phone", "इस फ़ोन से साइन आउट करें"), role: .destructive) { confirmSignOut = true }
                    }
                }
            }
            .navigationTitle(model.t("Settings", "सेटिंग्स"))
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(model.t("Done", "हो गया")) {
                        if API(server: server) != nil, server != model.server { model.server = server }
                        dismiss()
                    }
                }
            }
            .confirmationDialog(model.t("Sign out? VoiceMitra calls won't ring on this phone any more.",
                                        "साइन आउट करें? VoiceMitra की कॉल इस फ़ोन पर नहीं आएँगी।"),
                                isPresented: $confirmSignOut, titleVisibility: .visible) {
                Button(model.t("Sign out", "साइन आउट"), role: .destructive) {
                    Task {
                        await model.unpair()
                        dismiss()
                    }
                }
            }
            .onAppear { server = model.server }
        }
    }
}
