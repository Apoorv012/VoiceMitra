import Foundation

/// The events from /ws/patients/{id}/chat the app acts on (shapes: web/src/lib/events.ts).
enum PatientEvent {
    /// A voice call just started for this patient: ring.
    case voiceCall(VoiceJoin)
    /// Sent on connect; `voice` is set while a voice call is waiting or in progress.
    case snapshot(voice: VoiceJoin?)
    case voiceCallEnded
    /// Something changed that the home screen shows (a call ended, a dose was logged...).
    case refresh
}

/// Keeps the patient socket open while the app is in the foreground: reconnects with backoff, pings to
/// notice a dead connection. Call `start` when the app becomes active and `stop` when it leaves.
@MainActor
final class PatientSocket {
    var onEvent: (PatientEvent) -> Void = { _ in }
    private(set) var isConnected = false
    var onConnectedChange: (Bool) -> Void = { _ in }

    private var url: URL?
    private var task: URLSessionWebSocketTask?
    private var generation = 0
    private var attempt = 0
    private var pinger: Task<Void, Never>?

    func start(url: URL) {
        if self.url == url, task != nil { return }
        self.url = url
        attempt = 0
        open()
    }

    func stop() {
        url = nil
        close()
    }

    private func open() {
        close()
        guard let url else { return }
        generation += 1
        let gen = generation
        let t = URLSession.shared.webSocketTask(with: url)
        task = t
        t.resume()
        receive(gen)
        pinger = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(20))
                guard let self, gen == self.generation, let task = self.task else { return }
                task.sendPing { error in
                    if error != nil { Task { @MainActor in self.failed(gen) } }
                }
            }
        }
    }

    private func close() {
        generation += 1
        pinger?.cancel()
        pinger = nil
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        setConnected(false)
    }

    private func receive(_ gen: Int) {
        task?.receive { [weak self] result in
            Task { @MainActor in
                guard let self, gen == self.generation else { return }
                switch result {
                case .success(let message):
                    self.attempt = 0
                    self.setConnected(true)
                    switch message {
                    case .string(let text): self.handle(Data(text.utf8))
                    case .data(let data): self.handle(data)
                    @unknown default: break
                    }
                    self.receive(gen)
                case .failure:
                    self.failed(gen)
                }
            }
        }
    }

    private func failed(_ gen: Int) {
        guard gen == generation, url != nil else { return }
        pinger?.cancel()
        task?.cancel()
        task = nil
        setConnected(false)
        // 1, 2, 4, 8, 16, 30 s (+ up to 1 s jitter)
        let delay = min(30.0, pow(2.0, Double(attempt))) + Double.random(in: 0...1)
        attempt += 1
        let next = generation
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard let self, self.generation == next, self.url != nil else { return }
            self.open()
        }
    }

    private func setConnected(_ value: Bool) {
        guard value != isConnected else { return }
        isConnected = value
        onConnectedChange(value)
    }

    private func handle(_ data: Data) {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = obj["type"] as? String else { return }
        switch type {
        case "voice_call":
            if let join = Self.join(obj) { onEvent(.voiceCall(join)) }
        case "snapshot":
            onEvent(.snapshot(voice: (obj["voice"] as? [String: Any]).flatMap(Self.join)))
        case "voice_call_ended":
            onEvent(.voiceCallEnded)
        case "call_ended":
            onEvent(.refresh)
        default:
            break
        }
    }

    private static func join(_ obj: [String: Any]) -> VoiceJoin? {
        guard let url = obj["url"] as? String, let token = obj["token"] as? String else { return nil }
        return VoiceJoin(callId: obj["call_id"] as? String, url: url, token: token)
    }
}
