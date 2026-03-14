import Foundation

/// In-memory auth service for SwiftUI previews and tests.
struct InMemoryAuthService: AuthService {
    private let delay: TimeInterval

    init(delay: TimeInterval = 0.3) {
        self.delay = delay
    }

    func signUp(email: String, password: String, name: String) async throws -> AuthResult {
        try await Task.sleep(for: .seconds(delay))
        return .confirmationRequired(email: email)
    }

    func signIn(email: String, password: String) async throws -> AuthSession {
        try await Task.sleep(for: .seconds(delay))
        return AuthSession(
            accessToken: "preview-access-token",
            idToken: "preview-id-token",
            refreshToken: "preview-refresh-token",
            tenantId: "t_preview_tenant",
            userSub: "preview-sub-123",
            email: email,
            expiresAt: Date().addingTimeInterval(3600)
        )
    }

    func confirmSignUp(email: String, code: String) async throws {
        try await Task.sleep(for: .seconds(delay))
    }

    func resendConfirmationCode(email: String) async throws {
        try await Task.sleep(for: .seconds(delay))
    }

    func signOut() async {}

    func refreshSession() async throws -> AuthSession {
        try await Task.sleep(for: .seconds(delay))
        return AuthSession(
            accessToken: "preview-refreshed-token",
            idToken: "preview-id-token",
            refreshToken: "preview-refresh-token",
            tenantId: "t_preview_tenant",
            userSub: "preview-sub-123",
            email: "preview@cawnex.io",
            expiresAt: Date().addingTimeInterval(3600)
        )
    }

    func currentSession() async -> AuthSession? {
        AuthSession(
            accessToken: "preview-access-token",
            idToken: "preview-id-token",
            refreshToken: "preview-refresh-token",
            tenantId: "t_preview_tenant",
            userSub: "preview-sub-123",
            email: "preview@cawnex.io",
            expiresAt: Date().addingTimeInterval(3600)
        )
    }
}
