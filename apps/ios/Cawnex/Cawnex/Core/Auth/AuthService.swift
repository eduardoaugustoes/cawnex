import Foundation

// MARK: - Auth Models

struct AuthSession: Equatable {
    let accessToken: String
    let idToken: String
    let refreshToken: String
    let tenantId: String
    let userSub: String
    let email: String
    let expiresAt: Date

    var isExpired: Bool {
        Date() >= expiresAt
    }
}

enum AuthResult: Equatable {
    case signedIn(AuthSession)
    case confirmationRequired(email: String)
}

enum AuthError: LocalizedError {
    case invalidCredentials
    case userNotConfirmed
    case userAlreadyExists
    case codeMismatch
    case expiredCode
    case networkError(String)
    case missingTenantId
    case unknown(String)

    var errorDescription: String? {
        switch self {
        case .invalidCredentials: "Invalid email or password."
        case .userNotConfirmed: "Please confirm your email first."
        case .userAlreadyExists: "An account with this email already exists."
        case .codeMismatch: "Invalid confirmation code."
        case .expiredCode: "Confirmation code has expired. Please request a new one."
        case .networkError(let msg): msg
        case .missingTenantId: "Account setup incomplete. Please contact support."
        case .unknown(let msg): msg
        }
    }
}

// MARK: - Protocol

protocol AuthService: Sendable {
    func signUp(email: String, password: String, name: String) async throws -> AuthResult
    func signIn(email: String, password: String) async throws -> AuthSession
    func confirmSignUp(email: String, code: String) async throws -> Void
    func resendConfirmationCode(email: String) async throws -> Void
    func signOut() async
    func refreshSession() async throws -> AuthSession
    func currentSession() async -> AuthSession?
}
