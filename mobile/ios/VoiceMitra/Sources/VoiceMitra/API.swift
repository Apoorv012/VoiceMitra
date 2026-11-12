import Foundation

// The backend calls the app makes, per ../../API.md. JSON keys are snake_case; decoded with
// .convertFromSnakeCase, so `next_dose` arrives as `nextDose`.

// MARK: - Response shapes (subset of backend/views.py and backend/routers/*.py)

struct Person: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let age: Int?
    let description: String?
}

struct Slot: Decodable, Identifiable {
    let dosageId: String
    let medicine: String
    let dose: String
    let at: Date
    /// taken|partial|missed|later|unknown|skipped|upcoming|due|no_checkin
    let state: String
    let note: String?

    var id: String { "\(dosageId)@\(at.timeIntervalSince1970)" }
}

struct Adherence: Decodable {
    let taken: Int
    let missed: Int
    let unrecorded: Int
    let rate: Int?
}

struct Checkin: Decodable, Identifiable {
    let callId: String
    let at: Date
    let type: String
    /// taken|not_taken|confusion|dont_know
    let medicineStatus: String?
    let summary: String?
    let symptoms: [String]
    let seriousness: Int?
    let escalated: Bool
    /// ok|remedy|urgent
    let patientStatus: String?
    let doctorConnected: Bool?

    var id: String { callId }
}

/// A message sent to the family contact (History shows them between the check-ins).
struct FamilyAlert: Decodable, Identifiable {
    let id: String
    let at: Date
    let message: String
    let caregiver: String?
    /// unreachable|escalation
    let trigger: String
    let urgent: Bool
}

struct HowDoing: Decodable {
    let at: Date
    let summary: String
    /// ok|watch|urgent
    let band: String
}

struct CaregiverView: Decodable {
    let name: String
    let relation: String
    let phoneNumber: String
}

/// One day of the week strip: good|mixed|missed|unknown|upcoming|none.
struct DayView: Decodable, Identifiable {
    let date: String
    let state: String
    let taken: Int
    let due: Int

    var id: String { date }
}

struct PatientHome: Decodable {
    let timezone: String
    let patient: Person
    let allergies: [String]
    let today: [Slot]
    let nextDose: Slot?
    let week: [DayView]
    let adherence: Adherence
    let lastCheckin: Checkin?
    let howDoing: HowDoing?
    let reminders: [Date]
    let caregiver: CaregiverView?
}

struct MedicineView: Decodable, Identifiable {
    let dosageId: String
    let name: String
    let dose: String
    /// daily|weekly|every_x_day|fixed_times
    let frequency: String
    let intervalDays: Int?
    let times: [String]
    let active: Bool
    let daysLeft: Int?
    /// Last 7 days.
    let taken: Int
    let known: Int

    var id: String { dosageId }
}

struct PatientMedicines: Decodable {
    let allergies: [String]
    let medicines: [MedicineView]
}

struct PatientHistory: Decodable {
    let timezone: String?
    let checkins: [Checkin]
    let alerts: [FamilyAlert]?
}

struct PairRequest: Encodable {
    let code: String
    let platform = "ios"
    let pushToken: String? = nil
    let name: String

    enum CodingKeys: String, CodingKey { case code, platform, pushToken = "push_token", name }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(code, forKey: .code)
        try c.encode(platform, forKey: .platform)
        try c.encodeNil(forKey: .pushToken) // the contract sends an explicit null: no push on a free Apple ID
        try c.encode(name, forKey: .name)
    }
}

/// POST /api/auth/login -- answers with the same shape as pairing (PairResponse).
struct LoginRequest: Encodable {
    let username: String
    let password: String
    let platform = "ios"
    let name: String

    enum CodingKeys: String, CodingKey { case username, password, platform, pushToken = "push_token", name }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(username, forKey: .username)
        try c.encode(password, forKey: .password)
        try c.encode(platform, forKey: .platform)
        try c.encodeNil(forKey: .pushToken)
        try c.encode(name, forKey: .name)
    }
}

struct PairResponse: Decodable {
    let deviceId: String
    let deviceToken: String
    let patientId: String
    let patientName: String
}

struct DeviceInfo: Decodable {
    let deviceId: String
    let patientId: String
    let patientName: String
}

/// How to join a voice call: from GET .../voice-call, the socket's `voice_call` event or a snapshot's `voice`.
struct VoiceJoin: Decodable, Equatable {
    let callId: String?
    let url: String
    let token: String
}

// MARK: - Client

struct APIError: LocalizedError {
    let status: Int
    let detail: String
    var errorDescription: String? { "\(detail) (\(status))" }
    /// 401/404 on an X-Device-Token endpoint: the pairing is gone (API.md), pair again.
    var pairingGone: Bool { status == 401 || status == 404 }
}

/// Once signed in, every request -- and the patient socket's handshake -- carries the phone's `X-Device-Token`:
/// the server tells a phone nothing about a patient without it (mobile/API.md).
struct API {
    let base: URL
    let deviceToken: String?

    init?(server: String, deviceToken: String? = nil) {
        self.deviceToken = deviceToken
        let trimmed = server.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed.hasSuffix("/") ? String(trimmed.dropLast()) : trimmed),
              let scheme = url.scheme, scheme == "http" || scheme == "https", url.host != nil else { return nil }
        base = url
    }

    /// wss://<host>/ws/patients/{id}/chat, with the device token on the handshake.
    func patientSocketRequest(patientId: String) -> URLRequest? {
        guard var c = URLComponents(url: base.appendingPathComponent("ws/patients/\(patientId)/chat"),
                                    resolvingAgainstBaseURL: false) else { return nil }
        c.scheme = base.scheme == "https" ? "wss" : "ws"
        guard let url = c.url else { return nil }
        var r = URLRequest(url: url)
        if let deviceToken { r.setValue(deviceToken, forHTTPHeaderField: "X-Device-Token") }
        return r
    }

    func home(patientId: String) async throws -> PatientHome {
        try await send("GET", "api/app/patients/\(patientId)/home")
    }

    func medicines(patientId: String) async throws -> PatientMedicines {
        try await send("GET", "api/app/patients/\(patientId)/medicines")
    }

    func history(patientId: String) async throws -> PatientHistory {
        try await send("GET", "api/app/patients/\(patientId)/history")
    }

    func pair(code: String, name: String) async throws -> PairResponse {
        try await send("POST", "api/devices/pair", body: PairRequest(code: code, name: name))
    }

    func login(username: String, password: String, name: String) async throws -> PairResponse {
        try await send("POST", "api/auth/login", body: LoginRequest(username: username, password: password, name: name))
    }

    func device(_ id: String, token: String) async throws -> DeviceInfo {
        try await send("GET", "api/devices/\(id)", token: token)
    }

    func unpair(_ id: String, token: String) async throws {
        try await sendEmpty("DELETE", "api/devices/\(id)", token: token)
    }

    /// Talk now. The device token tells the backend not to ring the phone that started the call.
    func startVoiceCall(patientId: String, token: String?) async throws {
        try await sendEmpty("POST", "api/patients/\(patientId)/voice-call", token: token)
    }

    /// Join details for the call in progress; nil when there is none (404).
    func voiceCall(patientId: String) async throws -> VoiceJoin? {
        do {
            return try await send("GET", "api/patients/\(patientId)/voice-call") as VoiceJoin
        } catch let e as APIError where e.status == 404 {
            return nil
        }
    }

    /// Decline a ring / hang up.
    func endCall(patientId: String) async throws {
        try await sendEmpty("POST", "api/patients/\(patientId)/call/end")
    }

    // MARK: plumbing

    private func request(_ method: String, _ path: String, token: String?, body: Data?) -> URLRequest {
        var r = URLRequest(url: base.appendingPathComponent(path), timeoutInterval: 20)
        r.httpMethod = method
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token = token ?? deviceToken { r.setValue(token, forHTTPHeaderField: "X-Device-Token") }
        if let body {
            r.httpBody = body
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return r
    }

    private func perform(_ r: URLRequest) async throws -> Data {
        let (data, response) = try await URLSession.shared.data(for: r)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            throw APIError(status: status, detail: Self.detail(from: data) ?? HTTPURLResponse.localizedString(forStatusCode: status))
        }
        return data
    }

    private func send<T: Decodable>(_ method: String, _ path: String, token: String? = nil) async throws -> T {
        try JSON.decoder.decode(T.self, from: await perform(request(method, path, token: token, body: nil)))
    }

    private func send<T: Decodable, B: Encodable>(_ method: String, _ path: String, token: String? = nil, body: B) async throws -> T {
        let data = try JSONEncoder().encode(body)
        return try JSON.decoder.decode(T.self, from: await perform(request(method, path, token: token, body: data)))
    }

    private func sendEmpty(_ method: String, _ path: String, token: String? = nil) async throws {
        _ = try await perform(request(method, path, token: token, body: nil))
    }

    /// FastAPI errors: {"detail": "text"} or {"detail": [{"msg": ...}]} for validation errors.
    private static func detail(from data: Data) -> String? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        if let s = obj["detail"] as? String { return s }
        if let list = obj["detail"] as? [[String: Any]] { return list.compactMap { $0["msg"] as? String }.joined(separator: "; ") }
        return nil
    }
}

enum JSON {
    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        d.dateDecodingStrategy = .custom { decoder in
            let s = try decoder.singleValueContainer().decode(String.self)
            if let date = parseDate(s) { return date }
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath, debugDescription: "bad date \(s)"))
        }
        return d
    }()

    /// Python's isoformat: optional fraction of 1-6 digits, offset "+00:00"/"Z" or none (= UTC).
    static func parseDate(_ raw: String) -> Date? {
        var s = raw
        if let dot = s.firstIndex(of: ".") {
            var end = s.index(after: dot)
            while end < s.endIndex, s[end].isNumber { end = s.index(after: end) }
            let digits = s[s.index(after: dot)..<end]
            s.replaceSubrange(dot..<end, with: "." + String((digits + "000").prefix(3)))
        }
        let timePart = s.split(separator: "T").last ?? ""
        if !(timePart.contains("Z") || timePart.contains("+") || timePart.contains("-")) { s += "Z" }
        return withFraction.date(from: s) ?? plain.date(from: s)
    }

    private static let withFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let plain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()
}
