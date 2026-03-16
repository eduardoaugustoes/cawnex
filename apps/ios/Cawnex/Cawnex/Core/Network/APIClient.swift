import Foundation

/// Authenticated HTTP client for the Cawnex API.
/// Uses the JWT access token from the current auth session.
final class APIClient: @unchecked Sendable {
    private let authService: any AuthService
    private let session = URLSession.shared

    init(authService: any AuthService) {
        self.authService = authService
    }

    private var baseURL: String { AppConfiguration.apiBaseURL }

    // MARK: - HTTP Methods

    func get<T: Decodable>(_ path: String) async throws -> T {
        let request = try await buildRequest(path: path, method: "GET")
        return try await execute(request)
    }

    func post<T: Decodable>(_ path: String, body: some Encodable) async throws -> T {
        var request = try await buildRequest(path: path, method: "POST")
        request.httpBody = try JSONEncoder().encode(body)
        return try await execute(request)
    }

    func put<T: Decodable>(_ path: String, body: some Encodable) async throws -> T {
        var request = try await buildRequest(path: path, method: "PUT")
        request.httpBody = try JSONEncoder().encode(body)
        return try await execute(request)
    }

    // MARK: - Request Building

    private func buildRequest(path: String, method: String) async throws -> URLRequest {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL(path)
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Attach JWT
        guard let authSession = await authService.currentSession() else {
            throw APIError.notAuthenticated
        }
        request.setValue("Bearer \(authSession.idToken)", forHTTPHeaderField: "Authorization")

        return request
    }

    // MARK: - Execution

    private func execute<T: Decodable>(_ request: URLRequest) async throws -> T {
        #if DEBUG
        print("[API] \(request.httpMethod ?? "?") \(request.url?.path ?? "?")")
        #endif

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError("Invalid response")
        }

        #if DEBUG
        let bodyPreview = String(data: data, encoding: .utf8)?.prefix(500) ?? "nil"
        print("[API] \(httpResponse.statusCode) \(bodyPreview)")
        #endif

        guard (200...299).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpError(statusCode: httpResponse.statusCode, body: body)
        }

        return try JSONDecoder().decode(T.self, from: data)
    }
}

// MARK: - Errors

enum APIError: LocalizedError {
    case invalidURL(String)
    case notAuthenticated
    case networkError(String)
    case httpError(statusCode: Int, body: String)

    var errorDescription: String? {
        switch self {
        case .invalidURL(let path): "Invalid URL: \(path)"
        case .notAuthenticated: "Not authenticated. Please sign in."
        case .networkError(let msg): msg
        case .httpError(let code, let body): "Server error (\(code)): \(body)"
        }
    }
}
