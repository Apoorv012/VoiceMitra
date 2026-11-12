import AVFAudio
import Foundation
import Observation
import UIKit

/// App state: server, language, pairing, the home screen's data, and wiring between the patient socket and
/// the call center.
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

    let calls = CallCenter()
    @ObservationIgnored private let socket = PatientSocket()
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
        socket.onEvent = { [weak self] in self?.handle($0) }
        socket.onConnectedChange = { [weak self] in self?.socketConnected = $0 }
        syncCallContext()
    }

    /// Strings: `t("Taken", "ले ली")`.
    func t(_ en: String, _ hi: String) -> String { lang == .hi ? hi : en }

    // MARK: - Lifecycle (SPEC I4: the socket only while the app is in the foreground)

    func setActive(_ active: Bool) {
        isActive = active
        if active {
            reconnect()
            Task {
                await verifyPairing()
                await loadHome()
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
        guard isActive, let pairing, let request = api?.patientSocketRequest(patientId: pairing.patientId) else {
            socket.stop()
            return
        }
        socket.start(request: request)
    }

    private func syncCallContext() {
        calls.api = api
        calls.patientId = pairing?.patientId
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
        setPairing(Pairing(deviceId: r.deviceId, deviceToken: r.deviceToken, patientId: r.patientId, patientName: r.patientName))
    }

    /// Username + password (POST /api/auth/login): stored exactly like a pairing.
    func login(username: String, password: String) async throws {
        guard let api else { throw APIError(status: 0, detail: t("Check the server address", "सर्वर का पता जाँचें")) }
        let r = try await api.login(username: username.trimmingCharacters(in: .whitespaces), password: password,
                                    name: UIDevice.current.name)
        setPairing(Pairing(deviceId: r.deviceId, deviceToken: r.deviceToken, patientId: r.patientId, patientName: r.patientName))
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
        reconnect()
        if p != nil { Task { await loadHome() } }
    }

    /// On launch: still paired? 401/404 mean the pairing is gone (unpaired from the web, or a new code was used).
    private func verifyPairing() async {
        guard let p = pairing, let id = p.deviceId, let token = p.deviceToken, let api else { return }
        do {
            let info = try await api.device(id, token: token)
            if info.patientName != p.patientName {
                var updated = p
                updated.patientName = info.patientName
                Keychain.save(updated)
                pairing = updated
            }
        } catch let e as APIError where e.pairingGone {
            setPairing(nil)
        } catch {
            // Offline: keep the pairing.
        }
    }

    // MARK: - Home (SPEC I3)

    func loadHome() async {
        guard let p = pairing, let api else { return }
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
        guard let p = pairing, let api else { return }
        if let m = try? await api.medicines(patientId: p.patientId) { medicines = m }
    }

    func loadHistory() async {
        guard let p = pairing, let api else { return }
        if let h = try? await api.history(patientId: p.patientId) { history = h }
    }

    /// "Talk to VoiceMitra": start the call, then join it. The join details come from the socket's
    /// voice_call event or from GET .../voice-call, whichever is first.
    func talkNow() async {
        guard let p = pairing, let api, !talkBusy, calls.beginOwnCall() else { return }
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
}
