import SwiftUI

/// First screen: username + password (POST /api/auth/login); "Use a 6-digit code instead" switches to the
/// pairing code from the web (patient's Me tab -> "Connect a phone"). Both store the same pairing.
struct SignInView: View {
    @Environment(AppModel.self) private var model
    @State private var useCode = false
    @State private var showServer = false

    var body: some View {
        ScrollView {
            VStack(spacing: 26) {
                HStack {
                    Spacer()
                    LangToggle()
                }

                VStack(spacing: 14) {
                    ZStack {
                        Circle().fill(VM.sage).frame(width: 150, height: 150)
                        BrandMark(size: 88)
                    }
                    Text("VoiceMitra")
                        .font(.system(.largeTitle, design: .rounded, weight: .bold))
                        .foregroundStyle(VM.ink)
                    Text(model.t("Your medicine reminders and a friendly check-in call.",
                                 "आपकी दवा की याद और एक दोस्ताना बातचीत।"))
                        .font(.title3)
                        .foregroundStyle(VM.ink2)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 4)

                Group {
                    if useCode {
                        CodeForm()
                    } else {
                        PasswordForm()
                    }
                }
                .card(padding: 22)
                .transition(.opacity.combined(with: .move(edge: .bottom)))

                Button {
                    withAnimation(.easeInOut(duration: 0.2)) { useCode.toggle() }
                } label: {
                    Label(useCode ? model.t("Sign in with username and password", "यूज़रनेम और पासवर्ड से साइन इन करें")
                                  : model.t("Use a 6-digit code instead", "6 अंकों का कोड इस्तेमाल करें"),
                          systemImage: useCode ? "person.fill" : "number")
                }
                .buttonStyle(SecondaryButtonStyle())

                Button {
                    showServer = true
                } label: {
                    Label(model.t("Server settings", "सर्वर सेटिंग्स"), systemImage: "gearshape")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(VM.muted)
                }
                .buttonStyle(.plain)

            }
            .padding(.horizontal, 22)
            .padding(.vertical, 16)
            .frame(maxWidth: 560)
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(VM.page.ignoresSafeArea())
        .sheet(isPresented: $showServer) { ServerSettingsSheet() }
    }
}

// MARK: - Forms

@MainActor
private func offlineMessage(_ model: AppModel) -> String {
    model.t("Couldn't reach VoiceMitra. Check the internet and try again.",
            "VoiceMitra से संपर्क नहीं हो सका। इंटरनेट जाँचकर फिर कोशिश करें।")
}

private struct FormError: View {
    let text: String?

    var body: some View {
        if let text {
            Label(text, systemImage: "exclamationmark.circle.fill")
                .font(.body.weight(.semibold))
                .foregroundStyle(VM.critInk)
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: VM.radiusSmall, style: .continuous).fill(VM.critSoft))
                .transition(.opacity)
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
            HStack(spacing: 10) {
                if busy { ProgressView().tint(VM.onBtn) }
                Text(busy ? model.t("Signing in…", "साइन इन हो रहा है…") : title)
            }
        }
        .buttonStyle(PrimaryButtonStyle())
        .disabled(!enabled || busy)
    }
}

/// A labelled input with an icon, on the sunken colour (large text for older eyes).
private struct FieldBox<Field: View>: View {
    let label: String
    let icon: String
    let focused: Bool
    @ViewBuilder var field: Field

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(.headline).foregroundStyle(VM.ink2)
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(focused ? VM.accent : VM.muted)
                    .frame(width: 26)
                field
                    .font(.title3)
                    .foregroundStyle(VM.ink)
            }
            .padding(.horizontal, 16)
            .frame(minHeight: 60)
            .background(RoundedRectangle(cornerRadius: VM.radiusSmall, style: .continuous).fill(VM.sunken))
            .overlay(
                RoundedRectangle(cornerRadius: VM.radiusSmall, style: .continuous)
                    .strokeBorder(focused ? VM.accent : VM.line, lineWidth: focused ? 2 : 1)
            )
        }
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
            VStack(alignment: .leading, spacing: 6) {
                Text(model.t("Sign in", "साइन इन करें"))
                    .font(.title.bold())
                    .foregroundStyle(VM.ink)
                Text(model.t("Use the username and password set on the VoiceMitra website (Me → Phone app login).",
                             "VoiceMitra वेबसाइट पर बनाया यूज़रनेम और पासवर्ड डालें (मैं → फ़ोन ऐप लॉगिन)।"))
                    .font(.body)
                    .foregroundStyle(VM.muted)
            }

            FieldBox(label: model.t("Username", "यूज़रनेम"), icon: "person.fill", focused: field == .username) {
                TextField(model.t("e.g. sunita", "जैसे sunita"), text: $username)
                    .textContentType(.username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.next)
                    .focused($field, equals: .username)
                    .onSubmit { field = .password }
            }

            FieldBox(label: model.t("Password", "पासवर्ड"), icon: "lock.fill", focused: field == .password) {
                HStack {
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
                        Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                            .font(.title3)
                            .foregroundStyle(VM.muted)
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(showPassword ? model.t("Hide password", "पासवर्ड छिपाएँ")
                                                     : model.t("Show password", "पासवर्ड दिखाएँ"))
                }
            }

            FormError(text: error)

            SubmitButton(title: model.t("Sign in", "साइन इन करें"), busy: busy, enabled: canSubmit) {
                Task { await submit() }
            }
        }
        .animation(.easeOut(duration: 0.15), value: error)
    }

    private var canSubmit: Bool { !username.trimmingCharacters(in: .whitespaces).isEmpty && !password.isEmpty }

    private func submit() async {
        field = nil
        busy = true
        error = nil
        defer { busy = false }
        do {
            try await model.login(username: username, password: password)
        } catch let e as APIError where e.status == 401 {
            error = model.t("Wrong username or password. Please try again.", "यूज़रनेम या पासवर्ड गलत है। कृपया फिर कोशिश करें।")
        } catch let e as APIError where e.status == 403 && e.detail == "family_login" {
            // Right password, but a login for the website (backend/routers/auth.py): say where to use it.
            error = model.t("This is a family login. Family members use the website: open voicemitra.apoorvm.com in a browser.",
                            "यह परिवार वालों का लॉगिन है। परिवार वाले वेबसाइट इस्तेमाल करते हैं: ब्राउज़र में voicemitra.apoorvm.com खोलें।")
        } catch let e as APIError where e.status == 403 && e.detail == "staff_login" {
            error = model.t("This is a staff login. Staff use the website: voicemitra.apoorvm.com.",
                            "यह स्टाफ़ का लॉगिन है। स्टाफ़ वेबसाइट इस्तेमाल करता है: voicemitra.apoorvm.com।")
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
            VStack(alignment: .leading, spacing: 6) {
                Text(model.t("Connect with a code", "कोड से जोड़ें"))
                    .font(.title.bold())
                    .foregroundStyle(VM.ink)
                Text(model.t("On the VoiceMitra website, open Me → Connect a phone, and type the 6-digit code here.",
                             "VoiceMitra वेबसाइट पर मैं → फ़ोन जोड़ें खोलें और 6 अंकों का कोड यहाँ लिखें।"))
                    .font(.body)
                    .foregroundStyle(VM.muted)
            }

            // Six boxes over one hidden field (the number pad and SMS-style autofill still work).
            ZStack {
                TextField("", text: $code)
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    .focused($focused)
                    .opacity(0.02)
                    .onChange(of: code) { _, new in
                        let digits = String(new.filter(\.isNumber).prefix(6))
                        if digits != new { code = digits }
                        if digits.count == 6 { Task { await submit() } }
                    }
                HStack(spacing: 8) {
                    ForEach(0..<6, id: \.self) { i in
                        let chars = Array(code)
                        let active = focused && i == min(code.count, 5)
                        Text(i < chars.count ? String(chars[i]) : "")
                            .font(.system(size: 32, weight: .bold, design: .rounded))
                            .foregroundStyle(VM.ink)
                            .frame(maxWidth: .infinity, minHeight: 64)
                            .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(VM.sunken))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .strokeBorder(active ? VM.accent : VM.line, lineWidth: active ? 2 : 1)
                            )
                    }
                }
                .allowsHitTesting(false)
            }
            .contentShape(Rectangle())
            .onTapGesture { focused = true }
            .accessibilityElement()
            .accessibilityLabel(model.t("6-digit code", "6 अंकों का कोड"))
            .accessibilityValue(code)

            FormError(text: error)

            SubmitButton(title: model.t("Connect", "जोड़ें"), busy: busy, enabled: code.count == 6) {
                Task { await submit() }
            }
        }
        .onAppear { focused = true }
        .animation(.easeOut(duration: 0.15), value: error)
    }

    private func submit() async {
        guard !busy, code.count == 6 else { return }
        busy = true
        error = nil
        defer { busy = false }
        do {
            try await model.pair(code: code)
        } catch let e as APIError where e.status == 400 {
            error = model.t("That code is wrong or has expired. Get a new code and try again.",
                            "यह कोड गलत है या उसका समय निकल गया। नया कोड लेकर फिर कोशिश करें।")
            code = ""
        } catch let e as APIError where e.status == 429 {
            error = model.t("Too many wrong codes. Please try again later.",
                            "बहुत बार गलत कोड डाला गया। कृपया थोड़ी देर बाद फिर कोशिश करें।")
        } catch {
            self.error = offlineMessage(model)
        }
    }
}
