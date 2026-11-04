import AudioToolbox
import AVFoundation
import CallKit
import LiveKit
import Observation

/// One voice call at a time: the CallKit ring/answer screen, the LiveKit room, mute/speaker, hang-up.
///
/// Audio: CallKit owns the AVAudioSession. LiveKit's automatic session configuration is off and its audio
/// engine is only allowed to run between CallKit's didActivate and didDeactivate -- starting the engine on a
/// session CallKit hasn't activated yet is the classic "answered but silent" bug. If CallKit refuses a call
/// (SPEC I4 fallback), the app rings in-app and manages the session itself (`usingCallKit == false`).
@MainActor
@Observable
final class CallCenter: NSObject {
    enum Phase: Equatable { case idle, ringing, connecting, live }

    private(set) var phase: Phase = .idle
    private(set) var isMuted = false
    private(set) var isSpeaker = true
    private(set) var connectedAt: Date?
    /// Shown once on the home screen after a call fails.
    var error: String?
    /// CallKit refused the incoming call: the app shows its own full-screen ringing view.
    private(set) var inAppRinging = false
    /// Talk now was pressed and the call's join details haven't arrived yet.
    var awaitingOwnJoin: Bool { phase == .connecting && outgoing && join == nil }

    // Set by AppModel.
    @ObservationIgnored var api: API?
    @ObservationIgnored var patientId: String?
    @ObservationIgnored var lang: Lang = .en
    @ObservationIgnored var onFinished: () -> Void = {}

    @ObservationIgnored private let provider: CXProvider
    @ObservationIgnored private let controller = CXCallController()
    @ObservationIgnored private var uuid: UUID?
    @ObservationIgnored private var join: VoiceJoin?
    @ObservationIgnored private var outgoing = false
    @ObservationIgnored private var usingCallKit = true
    @ObservationIgnored private var room: Room?
    @ObservationIgnored private var seenCallIds: [String] = []
    @ObservationIgnored private var ringer: InAppRinger?

    override init() {
        let config = CXProviderConfiguration()
        config.supportsVideo = false
        config.maximumCallGroups = 1
        config.maximumCallsPerCallGroup = 1
        config.supportedHandleTypes = [.generic]
        config.includesCallsInRecents = false
        provider = CXProvider(configuration: config)
        super.init()
        provider.setDelegate(self, queue: nil) // main queue

        AudioManager.shared.audioSession.isAutomaticConfigurationEnabled = false
        try? AudioManager.shared.setEngineAvailability(.none)
    }

    // MARK: - Incoming (the patient socket's voice_call / snapshot.voice)

    func ring(_ join: VoiceJoin) {
        if let id = join.callId, seenCallIds.contains(id) { return }
        guard phase == .idle else { return }
        remember(join.callId)
        self.join = join
        outgoing = false
        usingCallKit = true
        error = nil
        let id = UUID()
        uuid = id
        phase = .ringing
        provider.reportNewIncomingCall(with: id, update: callUpdate()) { [weak self] err in
            guard let err else { return }
            Task { @MainActor in
                guard let self, self.uuid == id, self.phase == .ringing else { return }
                print("CallKit refused the call (\(err)); ringing in-app")
                self.uuid = nil
                self.usingCallKit = false
                self.inAppRinging = true
                self.ringer = InAppRinger()
                self.ringer?.start()
            }
        }
    }

    /// The in-app ringing view's buttons (only when CallKit refused the call).
    func answerInApp() {
        guard inAppRinging, let join else { return }
        stopRinging()
        configureSession()
        activateSessionManually()
        phase = .connecting
        Task { await connect(join) }
    }

    func declineInApp() {
        guard inAppRinging else { return }
        finish(notifyBackend: true)
    }

    // MARK: - Outgoing (Talk now)

    /// Shows the call as an outgoing CallKit call; the join details follow via `provideJoin`.
    @discardableResult
    func beginOwnCall() -> Bool {
        guard phase == .idle else { return false }
        outgoing = true
        usingCallKit = true
        join = nil
        error = nil
        phase = .connecting
        let id = UUID()
        uuid = id
        let action = CXStartCallAction(call: id, handle: CXHandle(type: .generic, value: "VoiceMitra"))
        controller.request(CXTransaction(action: action)) { [weak self] err in
            guard let err else { return }
            Task { @MainActor in
                guard let self, self.uuid == id else { return }
                print("CallKit refused the outgoing call (\(err)); managing audio in-app")
                self.uuid = nil
                self.usingCallKit = false
                self.configureSession()
                self.activateSessionManually()
            }
        }
        return true
    }

    func provideJoin(_ join: VoiceJoin) {
        guard awaitingOwnJoin else { return }
        remember(join.callId)
        self.join = join
        Task { await connect(join) }
    }

    func failOwnCall(_ message: String) {
        guard outgoing, phase != .idle else { return }
        error = message
        endViaCallKit(notifyBackend: true)
    }

    // MARK: - During the call

    func hangUp() { endViaCallKit(notifyBackend: true) }

    func toggleMute() {
        let muted = !isMuted
        if usingCallKit, let uuid {
            controller.request(CXTransaction(action: CXSetMutedCallAction(call: uuid, muted: muted))) { _ in }
        } else {
            applyMute(muted)
        }
    }

    func toggleSpeaker() {
        isSpeaker.toggle()
        applySpeaker()
    }

    /// voice_call_ended, or the room went away (agent finished, or another `patient` joined and pushed us out).
    func remoteEnded() {
        guard phase != .idle else { return }
        if usingCallKit, let uuid {
            provider.reportCall(with: uuid, endedAt: Date(), reason: phase == .ringing ? .unanswered : .remoteEnded)
        }
        finish(notifyBackend: false)
    }

    // MARK: - Internals

    private func connect(_ join: VoiceJoin) async {
        guard await AVAudioApplication.requestRecordPermission() else {
            error = lang == .hi ? "माइक्रोफ़ोन की अनुमति नहीं है। Settings में VoiceMitra के लिए माइक्रोफ़ोन चालू करें।"
                : "VoiceMitra can't use the microphone. Turn it on in Settings > VoiceMitra."
            endViaCallKit(notifyBackend: true)
            return
        }
        let room = Room()
        room.add(delegate: self)
        self.room = room
        do {
            try await room.connect(url: join.url, token: join.token)
            guard self.room === room else { await room.disconnect(); return }
            try await room.localParticipant.setMicrophone(enabled: !isMuted)
            guard self.room === room else { return }
            phase = .live
            connectedAt = Date()
            if usingCallKit, outgoing, let uuid { provider.reportOutgoingCall(with: uuid, connectedAt: connectedAt) }
        } catch {
            guard self.room === room else { return }
            print("LiveKit connect failed: \(error)")
            self.error = lang == .hi ? "कॉल नहीं जुड़ सकी। कृपया फिर कोशिश करें।" : "Couldn't connect the call. Please try again."
            endViaCallKit(notifyBackend: true)
        }
    }

    private func endViaCallKit(notifyBackend: Bool) {
        if usingCallKit, let uuid {
            // The provider's CXEndCallAction handler does the rest. If the request fails, clean up here.
            pendingEndNotifies = notifyBackend
            controller.request(CXTransaction(action: CXEndCallAction(call: uuid))) { [weak self] err in
                guard err != nil else { return }
                Task { @MainActor in
                    guard let self, self.uuid == uuid else { return }
                    self.provider.reportCall(with: uuid, endedAt: Date(), reason: .failed)
                    self.finish(notifyBackend: notifyBackend)
                }
            }
        } else {
            finish(notifyBackend: notifyBackend)
        }
    }

    @ObservationIgnored private var pendingEndNotifies = true

    private func finish(notifyBackend: Bool) {
        let oldRoom = room
        room = nil
        if let oldRoom { Task { await oldRoom.disconnect() } }
        if notifyBackend, let api, let patientId {
            Task { try? await api.endCall(patientId: patientId) }
        }
        stopRinging()
        if !usingCallKit {
            try? AudioManager.shared.setEngineAvailability(.none)
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
        uuid = nil
        join = nil
        outgoing = false
        usingCallKit = true
        pendingEndNotifies = true
        phase = .idle
        connectedAt = nil
        isMuted = false
        isSpeaker = true
        onFinished()
    }

    private func configureSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.playAndRecord, mode: .voiceChat, options: [.allowBluetoothHFP])
        } catch {
            print("audio session category failed: \(error)")
        }
    }

    private func activateSessionManually() {
        do {
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("audio session activate failed: \(error)")
        }
        try? AudioManager.shared.setEngineAvailability(.default)
        applySpeaker()
    }

    /// Speaker on by default (SPEC I5); the button switches to the earpiece.
    private func applySpeaker() {
        try? AVAudioSession.sharedInstance().overrideOutputAudioPort(isSpeaker ? .speaker : .none)
    }

    private func applyMute(_ muted: Bool) {
        isMuted = muted
        let room = room
        Task { try? await room?.localParticipant.setMicrophone(enabled: !muted) }
    }

    private func stopRinging() {
        ringer?.stop()
        ringer = nil
        inAppRinging = false
    }

    private func remember(_ callId: String?) {
        guard let callId else { return }
        seenCallIds.append(callId)
        if seenCallIds.count > 20 { seenCallIds.removeFirst() }
    }

    private func callUpdate() -> CXCallUpdate {
        let u = CXCallUpdate()
        u.remoteHandle = CXHandle(type: .generic, value: "VoiceMitra")
        u.localizedCallerName = "VoiceMitra"
        u.hasVideo = false
        u.supportsHolding = false
        u.supportsGrouping = false
        u.supportsUngrouping = false
        u.supportsDTMF = false
        return u
    }
}

// MARK: - CallKit (delegate queue = main)

extension CallCenter: CXProviderDelegate {
    nonisolated func providerDidReset(_ provider: CXProvider) {
        MainActor.assumeIsolated {
            if phase != .idle { finish(notifyBackend: true) }
        }
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXStartCallAction) {
        MainActor.assumeIsolated {
            configureSession()
            provider.reportOutgoingCall(with: action.callUUID, startedConnectingAt: Date())
            provider.reportCall(with: action.callUUID, updated: callUpdate())
        }
        action.fulfill()
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXAnswerCallAction) {
        MainActor.assumeIsolated {
            guard uuid == action.callUUID, phase == .ringing else {
                action.fail()
                return
            }
            configureSession()
            phase = .connecting
            let known = join
            let api = api, patientId = patientId
            action.fulfill()
            Task {
                // The ring carried the join details; fall back to asking the backend (API.md: GET .../voice-call).
                var target = known
                if target == nil, let api, let patientId { target = try? await api.voiceCall(patientId: patientId) }
                guard let target else { self.remoteEnded(); return }
                await self.connect(target)
            }
        }
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXEndCallAction) {
        MainActor.assumeIsolated {
            // Declining a ring and hanging up both tell the backend (POST .../call/end), unless the call
            // already ended on the backend's side (then CallKit gets reportCall(endedAt:) instead, not this).
            let notify = pendingEndNotifies
            if uuid == action.callUUID { finish(notifyBackend: notify) }
        }
        action.fulfill()
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXSetMutedCallAction) {
        MainActor.assumeIsolated { applyMute(action.isMuted) }
        action.fulfill()
    }

    nonisolated func provider(_ provider: CXProvider, didActivate audioSession: AVAudioSession) {
        MainActor.assumeIsolated {
            try? AudioManager.shared.setEngineAvailability(.default)
            applySpeaker()
        }
    }

    nonisolated func provider(_ provider: CXProvider, didDeactivate audioSession: AVAudioSession) {
        try? AudioManager.shared.setEngineAvailability(.none)
    }
}

// MARK: - LiveKit

extension CallCenter: RoomDelegate {
    nonisolated func room(_ room: Room, didDisconnectWithError error: LiveKitError?) {
        Task { @MainActor in
            guard self.room === room else { return }
            self.remoteEnded()
        }
    }
}

/// Fallback ring when CallKit refuses a call: vibrate + the system alert sound every 2 s.
@MainActor
final class InAppRinger {
    private var timer: Timer?

    func start() {
        tick()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { _ in
            Task { @MainActor in InAppRinger.buzz() }
        }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func tick() { Self.buzz() }

    private static func buzz() {
        AudioServicesPlayAlertSound(SystemSoundID(kSystemSoundID_Vibrate))
        AudioServicesPlayAlertSound(SystemSoundID(1005))
    }
}
