import Foundation
import Security

/// Lightweight Keychain wrapper for storing auth tokens.
/// No third-party dependencies — uses Security framework directly.
struct KeychainService {
    private let serviceName = "io.cawnex.auth"

    enum Key: String {
        case accessToken = "cawnex.accessToken"
        case idToken = "cawnex.idToken"
        case refreshToken = "cawnex.refreshToken"
    }

    func save(key: Key, data: String) {
        guard let data = data.data(using: .utf8) else { return }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key.rawValue,
        ]

        // Delete existing item first
        SecItemDelete(query as CFDictionary)

        var addQuery = query
        addQuery[kSecValueData as String] = data
        addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly

        SecItemAdd(addQuery as CFDictionary, nil)
    }

    func load(key: Key) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let string = String(data: data, encoding: .utf8) else {
            return nil
        }

        return string
    }

    func delete(key: Key) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key.rawValue,
        ]
        SecItemDelete(query as CFDictionary)
    }

    func deleteAll() {
        for key in [Key.accessToken, .idToken, .refreshToken] {
            delete(key: key)
        }
    }
}
