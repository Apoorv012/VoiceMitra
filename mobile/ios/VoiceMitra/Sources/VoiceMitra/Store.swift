import Foundation
import Security

enum Lang: String, CaseIterable {
    case en, hi
}

/// Small settings kept in UserDefaults (nothing secret).
enum Prefs {
    /// The tunnel's public HTTPS hostname (README: Cloudflare Tunnel sends /api and /ws to :8000).
    static let defaultServer = "https://voicemitra-api.apoorvm.com"  // the cloud API; the home tunnel is test-voicemitra

    static var server: String {
        get { UserDefaults.standard.string(forKey: "server_url") ?? defaultServer }
        set { UserDefaults.standard.set(newValue, forKey: "server_url") }
    }

    static var lang: Lang {
        get {
            if let raw = UserDefaults.standard.string(forKey: "lang"), let l = Lang(rawValue: raw) { return l }
            return Locale.preferredLanguages.first?.hasPrefix("hi") == true ? .hi : .en
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: "lang") }
    }
}

/// Who this phone belongs to: a device id + token from login or pairing. (Both are optional only because
/// older builds could store a debug "pick a patient" without them; such a pairing no longer works.)
struct Pairing: Codable, Equatable {
    var deviceId: String?
    var deviceToken: String?
    var patientId: String
    var patientName: String

    var isDevPick: Bool { deviceToken == nil }
}

/// The pairing lives in the Keychain (the device token is the only credential the app has).
enum Keychain {
    private static let service = "app.voicemitra.patient"
    private static let account = "pairing"

    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: account]
    }

    static func load() -> Pairing? {
        var q = query
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else { return nil }
        return try? JSONDecoder().decode(Pairing.self, from: data)
    }

    static func save(_ pairing: Pairing) {
        guard let data = try? JSONEncoder().encode(pairing) else { return }
        SecItemDelete(query as CFDictionary)
        var q = query
        q[kSecValueData as String] = data
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(q as CFDictionary, nil)
    }

    static func clear() {
        SecItemDelete(query as CFDictionary)
    }
}
