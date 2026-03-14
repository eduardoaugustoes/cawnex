import Foundation

/// Decodes JWT payload without verifying signature.
/// Signature verification is handled server-side by Cognito + API Gateway.
enum JWTParser {

    struct Claims {
        let sub: String
        let email: String
        let tenantId: String
        let exp: Date

        var isExpired: Bool {
            Date() >= exp
        }
    }

    static func decode(_ jwt: String) -> Claims? {
        let parts = jwt.split(separator: ".")
        guard parts.count == 3 else { return nil }

        guard let data = base64UrlDecode(String(parts[1])),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }

        let sub = json["sub"] as? String ?? ""
        let email = json["email"] as? String ?? ""
        let tenantId = json["custom:tenant_id"] as? String ?? ""
        let expTimestamp = json["exp"] as? TimeInterval ?? 0

        return Claims(
            sub: sub,
            email: email,
            tenantId: tenantId,
            exp: Date(timeIntervalSince1970: expTimestamp)
        )
    }

    private static func base64UrlDecode(_ string: String) -> Data? {
        var base64 = string
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")

        // Pad to multiple of 4
        let remainder = base64.count % 4
        if remainder > 0 {
            base64.append(contentsOf: String(repeating: "=", count: 4 - remainder))
        }

        return Data(base64Encoded: base64)
    }
}
