import Foundation

/// Authenticates against AWS Cognito using direct HTTP calls.
/// Uses USER_PASSWORD_AUTH flow — no SRP, no AWS SDK dependency.
/// Token storage via KeychainService, JWT parsing via JWTParser.
final class CognitoAuthService: AuthService, @unchecked Sendable {
    private let keychain: KeychainService
    private let session = URLSession.shared

    init(keychain: KeychainService = KeychainService()) {
        self.keychain = keychain
    }

    // MARK: - Sign Up

    func signUp(email: String, password: String, name: String) async throws -> AuthResult {
        let body: [String: Any] = [
            "ClientId": AppConfiguration.clientId,
            "Username": email,
            "Password": password,
            "UserAttributes": [
                ["Name": "email", "Value": email],
                ["Name": "name", "Value": name],
            ],
        ]

        do {
            let _: [String: Any] = try await cognitoRequest(action: "SignUp", body: body)
            return .confirmationRequired(email: email)
        } catch let error as AuthError {
            throw error
        }
    }

    // MARK: - Confirm Sign Up

    func confirmSignUp(email: String, code: String) async throws {
        let body: [String: Any] = [
            "ClientId": AppConfiguration.clientId,
            "Username": email,
            "ConfirmationCode": code,
        ]

        let _: [String: Any] = try await cognitoRequest(action: "ConfirmSignUp", body: body)
    }

    // MARK: - Resend Confirmation Code

    func resendConfirmationCode(email: String) async throws {
        let body: [String: Any] = [
            "ClientId": AppConfiguration.clientId,
            "Username": email,
        ]

        let _: [String: Any] = try await cognitoRequest(action: "ResendConfirmationCode", body: body)
    }

    // MARK: - Sign In

    func signIn(email: String, password: String) async throws -> AuthSession {
        let body: [String: Any] = [
            "ClientId": AppConfiguration.clientId,
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": [
                "USERNAME": email,
                "PASSWORD": password,
            ],
        ]

        let response: [String: Any] = try await cognitoRequest(action: "InitiateAuth", body: body)

        guard let result = response["AuthenticationResult"] as? [String: Any],
              let accessToken = result["AccessToken"] as? String,
              let idToken = result["IdToken"] as? String,
              let refreshToken = result["RefreshToken"] as? String else {
            throw AuthError.unknown("Missing authentication tokens in response")
        }

        let session = try buildSession(
            accessToken: accessToken,
            idToken: idToken,
            refreshToken: refreshToken
        )

        storeTokens(session)
        return session
    }

    // MARK: - Sign Out

    func signOut() async {
        keychain.deleteAll()
    }

    // MARK: - Refresh Session

    func refreshSession() async throws -> AuthSession {
        guard let refreshToken = keychain.load(key: .refreshToken) else {
            throw AuthError.invalidCredentials
        }

        let body: [String: Any] = [
            "ClientId": AppConfiguration.clientId,
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "AuthParameters": [
                "REFRESH_TOKEN": refreshToken,
            ],
        ]

        let response: [String: Any] = try await cognitoRequest(action: "InitiateAuth", body: body)

        guard let result = response["AuthenticationResult"] as? [String: Any],
              let accessToken = result["AccessToken"] as? String,
              let idToken = result["IdToken"] as? String else {
            throw AuthError.unknown("Missing tokens in refresh response")
        }

        // Refresh response doesn't include a new refresh token — reuse existing
        let session = try buildSession(
            accessToken: accessToken,
            idToken: idToken,
            refreshToken: refreshToken
        )

        storeTokens(session)
        return session
    }

    // MARK: - Current Session

    func currentSession() async -> AuthSession? {
        guard let accessToken = keychain.load(key: .accessToken),
              let idToken = keychain.load(key: .idToken),
              let refreshToken = keychain.load(key: .refreshToken) else {
            return nil
        }

        guard let session = try? buildSession(
            accessToken: accessToken,
            idToken: idToken,
            refreshToken: refreshToken
        ) else {
            return nil
        }

        if session.isExpired {
            return try? await refreshSession()
        }

        return session
    }

    // MARK: - Private Helpers

    private func buildSession(accessToken: String, idToken: String, refreshToken: String) throws -> AuthSession {
        guard let claims = JWTParser.decode(idToken) else {
            throw AuthError.unknown("Failed to parse ID token")
        }

        guard !claims.tenantId.isEmpty else {
            throw AuthError.missingTenantId
        }

        return AuthSession(
            accessToken: accessToken,
            idToken: idToken,
            refreshToken: refreshToken,
            tenantId: claims.tenantId,
            userSub: claims.sub,
            email: claims.email,
            expiresAt: claims.exp
        )
    }

    private func storeTokens(_ session: AuthSession) {
        keychain.save(key: .accessToken, data: session.accessToken)
        keychain.save(key: .idToken, data: session.idToken)
        keychain.save(key: .refreshToken, data: session.refreshToken)
    }

    /// Send a request to the Cognito JSON API.
    private func cognitoRequest<T>(action: String, body: [String: Any]) async throws -> T {
        let url = URL(string: AppConfiguration.cognitoEndpoint)!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-amz-json-1.1", forHTTPHeaderField: "Content-Type")
        request.setValue("AWSCognitoIdentityProviderService.\(action)", forHTTPHeaderField: "X-Amz-Target")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthError.networkError("Invalid response")
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw AuthError.networkError("Failed to parse response")
        }

        if httpResponse.statusCode != 200 {
            throw mapCognitoError(json, statusCode: httpResponse.statusCode)
        }

        guard let result = json as? T else {
            throw AuthError.unknown("Unexpected response type")
        }

        return result
    }

    private func mapCognitoError(_ json: [String: Any], statusCode: Int) -> AuthError {
        let type = (json["__type"] as? String ?? "")
            .split(separator: "#").last.map(String.init) ?? ""
        let message = json["message"] as? String ?? json["Message"] as? String ?? "Unknown error"

        switch type {
        case "NotAuthorizedException":
            return .invalidCredentials
        case "UserNotConfirmedException":
            return .userNotConfirmed
        case "UsernameExistsException":
            return .userAlreadyExists
        case "CodeMismatchException":
            return .codeMismatch
        case "ExpiredCodeException":
            return .expiredCode
        default:
            return .unknown(message)
        }
    }
}
