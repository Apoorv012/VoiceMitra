import AVFAudio
import Foundation
import Observation
import UIKit

/// App state: server, language, pairing, the home screen's data, and wiring between the live socket and
/// the call center. A caregiver (family contact) signed in on this phone gets the caregiver home instead of the
/// patient's tabs: their own socket, no ringing, no Talk now (API.md "Caregivers in the apps", C1).
@MainActor
@Observable
final class AppModel {
    var server: String { didSet { Prefs.server = server; reconnect() } }
    var lang: Lang { didSet { Prefs.lang = lang; calls.lang = lang } }
    private(set) var pairing: Pairing?

    private(set) var home: PatientHome?
    private(set) var medicines: PatientMedicines?
    private(set) var history: PatientHistory?
    private(set) var homeError: String?
    private(set) var loadingHome = false
    private(set) var socketConnected = false
    private(set) var talkBusy = false

    // Caregiver session (pairing.isCaregiver)
    private(set) var caregiverHome: CaregiverHome?
    private(set) var caregiverError: String?
    /// The alert being marked as seen ("all" for Mark all), while the request runs.
    private(set) var seenBusy: String?
    var seenError: String?
    /// Shown on the sign-in screen after the server dropped this login (e.g. no longer the family contact).
    var signInNotice: String?

    let calls = CallCenter()
    @ObservationIgnored private let socket = LiveSocket()
    @ObservationIgnored private var isActive = false

    var api: API? { API(server: server, deviceToken: pairing?.deviceToken) }

    init() {
        server = Prefs.server
        lang = Prefs.lang
        pairing = Keychain.load()
        calls.lang = lang
        calls.onFinished = { [weak self] in
            guard let self else { return }
            if !self.isActive { self.socket.stop() } // the call kept it open in the background
            Task {
                await self.loadHome()
                await self.loadHistory()
            }
        }
        socket.onMessage = { [weak self] type, obj in self?.handle(type: type, obj) }
        socket.onConnectedChange = { [weak self] in self?.socketConnected = $0 }
        syncCallContext()
    }

    var isCaregiver: Bool { pairing?.isCaregiver == true }

    /// Strings: `t("Taken", "ले ली")`.
    func t(_ en: String, _ hi: String) -> String { lang == .hi ? hi : en }

    // MARK: - Lifecycle (SPEC I4: the socket only while the app is in the foreground)

    func setActive(_ active: Bool) {
        isActive = active
        if active {
            reconnect()
            Task {
                await verifyPairing()
                await refresh()
            }
        } else if calls.phase == .idle {
            // In the background the app can't ring anyway (SPEC I4). During a call (screen locked, background
            // audio keeps the app alive) the socket stays, so voice_call_ended still arrives.
            socket.stop()
        }
    }

    /// Ask for the microphone before the first call, not in the middle of answering one.
    func askForMicrophone() async {
        _ = await AVAudioApplication.requestRecordPermission()
    }

    private func reconnect() {
        syncCallContext()
        guard isActive, let request = socketRequest() else {
            socket.stop()
            return
        }
        socket.start(request: request)
    }

    /// The patient's own socket (rings), or the caregiver's (refetch the caregiver home).
    private func socketRequest() -> URLRequest? {
        guard let pairing, let api else { return nil }
        if pairing.isCaregiver, let cgId = pairing.caregiverId {
            return api.caregiverSocketRequest(caregiverId: cgId)
        }
        return api.patientSocketRequest(patientId: pairing.patientId)
    }

    /// A caregiver phone never rings or hangs up a patient's call, so the call center gets nothing to act on.
    private func syncCallContext() {
        calls.api = isCaregiver ? nil : api
        calls.patientId = isCaregiver ? nil : pairing?.patientId
    }

    private func handle(type: String, _ obj: [String: Any]) {
        if isCaregiver {
            // snapshot | alert | alerts_seen | call_started | call_ended: each one means "refetch the home".
            Task { await loadCaregiverHome() }
        } else if let event = PatientEvent.parse(type: type, obj) {
            handle(event)
        }
    }

    private func handle(_ event: PatientEvent) {
        switch event {
        case .voiceCall(let join), .snapshot(voice: .some(let join)):
            if calls.awaitingOwnJoin {
                calls.provideJoin(join)
            } else {
                calls.ring(join)
            }
        case .voiceCallEnded:
            calls.remoteEnded()
            Task { await loadHome() }
        case .snapshot(voice: .none), .refresh:
            Task { await loadHome() }
        }
    }

    // MARK: - Pairing (SPEC I2)

    func pair(code: String) async throws {
        guard let api else { throw APIError(status: 0, detail: t("Check the server address", "सर्वर का पता जाँचें")) }
        let digits = code.filter(\.isNumber)
        let r = try await api.pair(code: digits, name: UIDevice.current.name)
        setPairing(r.pairing)
    }

    /// Username + password (POST /api/auth/login): stored exactly like a pairing. A caregiver's login answers
    /// with `role: "caregiver"` and their `caregiver_id`, which opens the caregiver home.
    func login(username: String, password: String) async throws {
        guard let api else { throw APIError(status: 0, detail: t("Check the server address", "सर्वर का पता जाँचें")) }
        let r = try await api.login(username: username.trimmingCharacters(in: .whitespaces), password: password,
                                    name: UIDevice.current.name)
        setPairing(r.pairing)
    }

    func unpair() async {
        if let p = pairing, let id = p.deviceId, let token = p.deviceToken, let api {
            try? await api.unpair(id, token: token)
        }
        setPairing(nil)
    }

    private func setPairing(_ p: Pairing?) {
        if let p { Keychain.save(p) } else { Keychain.clear() }
        pairing = p
        home = nil
        medicines = nil
        history = nil
        homeError = nil
        caregiverHome = nil
        caregiverError = nil
        seenError = nil
        if p != nil { signInNotice = nil }
        reconnect()
        if p != nil { Task { await refresh() } }
    }

    /// The server dropped this login: forget it, and for a caregiver say why on the sign-in screen.
    private func signedOutByServer(removedFamilyContact: Bool) {
        if removedFamilyContact {
            signInNotice = t("You're no longer the family contact for this patient.",
                             "अब आप इस मरीज़ के परिवार के संपर्क नहीं हैं।")
        }
        setPairing(nil)
    }

    /// Reload whatever the current screen shows.
    func refresh() async {
        if isCaregiver { await loadCaregiverHome() } else { await loadHome() }
    }

    /// On launch: still paired? 401/404 mean the pairing is gone (unpaired from the web, or a new code was used).
    private func verifyPairing() async {
        guard let p = pairing, let id = p.deviceId, let token = p.deviceToken, let api else { return }
        do {
            let info = try await api.device(id, token: token)
            var updated = p
            updated.patientId = info.patientId
            updated.patientName = info.patientName
            updated.role = info.role ?? "patient"
            updated.caregiverId = info.caregiverId
            updated.caregiverName = info.caregiverName
            guard pairing == p, updated != p else { return }
            if updated.isCaregiver != p.isCaregiver || updated.caregiverId != p.caregiverId || updated.patientId != p.patientId {
                setPairing(updated) // another screen and socket: start over
            } else {
                Keychain.save(updated)
                pairing = updated
            }
        } catch let e as APIError where e.pairingGone {
            // For a caregiver, 404 = removed as the family contact (API.md C1).
            if pairing == p { signedOutByServer(removedFamilyContact: p.isCaregiver && e.status == 404) }
        } catch {
            // Offline: keep the pairing.
        }
    }

    // MARK: - Home (SPEC I3)

    func loadHome() async {
        guard let p = pairing, !p.isCaregiver, let api else { return }
        loadingHome = true
        defer { loadingHome = false }
        do {
            home = try await api.home(patientId: p.patientId)
            homeError = nil
        } catch {
            homeError = t("Couldn't load this. Please check your connection.", "यह लोड नहीं हो सका। कृपया अपना इंटरनेट जाँचें।")
        }
    }

    func loadMedicines() async {
        guard let p = pairing, !p.isCaregiver, let api else { return }
        if let m = try? await api.medicines(patientId: p.patientId) { medicines = m }
    }

    /// Add one of the patient's own medicines (`editing` nil) or change one; then reload the list.
    func saveOwnMedicine(_ body: OwnMedicineBody, editing: MedicineView?) async throws {
        guard let p = pairing, !p.isCaregiver, let api else { throw APIError(status: 0, detail: "not signed in") }
        if let editing {
            try await api.updateMedicine(patientId: p.patientId, dosageId: editing.dosageId, body: body)
        } else {
            try await api.addOwnMedicine(patientId: p.patientId, body: body)
        }
        await loadMedicines()
    }

    /// Remove one of the patient's own medicines; returns "stopped" or "deleted".
    func removeMedicine(_ m: MedicineView) async throws -> String {
        guard let p = pairing, !p.isCaregiver, let api else { throw APIError(status: 0, detail: "not signed in") }
        let res = try await api.removeMedicine(patientId: p.patientId, dosageId: m.dosageId)
        await loadMedicines()
        return res.outcome
    }

    func loadHistory() async {
        guard let p = pairing, !p.isCaregiver, let api else { return }
        if let h = try? await api.history(patientId: p.patientId) { history = h }
    }

    /// "Talk to VoiceMitra": start the call, then join it. The join details come from the socket's
    /// voice_call event or from GET .../voice-call, whichever is first.
    func talkNow() async {
        guard let p = pairing, !p.isCaregiver, let api, !talkBusy, calls.beginOwnCall() else { return }
        talkBusy = true
        defer { talkBusy = false }
        do {
            try await api.startVoiceCall(patientId: p.patientId, token: p.deviceToken)
        } catch {
            calls.failOwnCall(t("Couldn't start the call. Please try again.", "कॉल शुरू नहीं हो सकी। कृपया फिर कोशिश करें।"))
            return
        }
        for _ in 0..<20 where calls.awaitingOwnJoin {
            if let join = try? await api.voiceCall(patientId: p.patientId) {
                calls.provideJoin(join)
                return
            }
            try? await Task.sleep(for: .milliseconds(500))
        }
        if calls.awaitingOwnJoin {
            calls.failOwnCall(t("Couldn't start the call. Please try again.", "कॉल शुरू नहीं हो सकी। कृपया फिर कोशिश करें।"))
        }
    }

    // MARK: - Caregiver home (API.md C1)

    func loadCaregiverHome() async {
        guard let p = pairing, p.isCaregiver, let cgId = p.caregiverId, let api else { return }
        do {
            let h = try await api.caregiverHome(caregiverId: cgId)
            guard pairing == p else { return }
            caregiverHome = h
            caregiverError = nil
        } catch let e as APIError where e.pairingGone {
            // 404: no longer this patient's family contact; 401: the login is gone. Either way: sign-in.
            if pairing == p { signedOutByServer(removedFamilyContact: e.status == 404) }
        } catch {
            guard pairing == p else { return }
            caregiverError = t("Couldn't load this. Please check your connection.", "यह लोड नहीं हो सका। कृपया अपना इंटरनेट जाँचें।")
        }
    }

    /// Mark one alert as seen, or all of them (`alertId` nil), then refetch.
    func markSeen(_ alertId: String?) async {
        guard let p = pairing, p.isCaregiver, let cgId = p.caregiverId, let api, seenBusy == nil else { return }
        seenBusy = alertId ?? "all"
        defer { seenBusy = nil }
        do {
            try await api.markAlertsSeen(caregiverId: cgId, alertId: alertId)
            seenError = nil
        } catch let e as APIError where e.status == 401 {
            if pairing == p { signedOutByServer(removedFamilyContact: false) }
            return
        } catch {
            // A 404 here is checked by the refetch below (the home answers 404 too if they were removed).
            seenError = t("Couldn't save that. Please try again.", "यह सेव नहीं हो सका। कृपया फिर कोशिश करें।")
        }
        await loadCaregiverHome()
    }
}
