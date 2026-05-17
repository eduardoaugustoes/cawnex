import Foundation

/// REST implementation: uses the shared APIClient. The fetchSession path
/// decodes via a configured JSONDecoder (ISO8601 dates); approve/reject
/// only care about HTTP status, so they go through a raw URLSession to
/// avoid forcing a Decodable response type through APIClient.
final class APIWaveReviewService: WaveReviewService {
    private let client: APIClient
    private let session = URLSession.shared

    init(client: APIClient) {
        self.client = client
    }

    // MARK: - Fetch

    func fetchSession(
        projectId: String, sessionId: String
    ) async throws -> CouncilSession {
        let path = "/projects/\(projectId)/council/sessions/\(sessionId)"
        do {
            let raw: Data = try await getRaw(path: path)
            return try Self.decoder().decode(CouncilSession.self, from: raw)
        } catch APIError.httpError(let code, let body) where code == 404 {
            throw WaveReviewError.notFound(sessionId: sessionId)
        } catch let APIError.httpError(code, body) {
            throw WaveReviewError.networkFailure(
                message: "HTTP \(code): \(body.prefix(200))"
            )
        } catch APIError.notAuthenticated {
            throw WaveReviewError.networkFailure(message: "Not authenticated")
        }
    }

    // MARK: - Mutate

    func approveWave(projectId: String, waveId: String) async throws {
        let path = "/projects/\(projectId)/waves/\(waveId)/approve"
        do {
            _ = try await postRaw(path: path, body: Data())
        } catch let APIError.httpError(code, body) {
            throw WaveReviewError.approveFailed(
                detail: "HTTP \(code): \(body.prefix(200))"
            )
        } catch APIError.notAuthenticated {
            throw WaveReviewError.approveFailed(detail: "Not authenticated")
        }
    }

    func rejectWave(
        projectId: String, waveId: String, reason: String
    ) async throws {
        let path = "/projects/\(projectId)/waves/\(waveId)/reject"
        let body = try JSONEncoder().encode(["reason": reason])
        do {
            _ = try await postRaw(path: path, body: body)
        } catch let APIError.httpError(code, body) {
            throw WaveReviewError.rejectFailed(
                detail: "HTTP \(code): \(body.prefix(200))"
            )
        } catch APIError.notAuthenticated {
            throw WaveReviewError.rejectFailed(detail: "Not authenticated")
        }
    }

    // MARK: - Internal raw helpers

    private func getRaw(path: String) async throws -> Data {
        try await rawRequest(path: path, method: "GET", body: nil)
    }

    private func postRaw(path: String, body: Data) async throws -> Data {
        try await rawRequest(path: path, method: "POST", body: body)
    }

    private func rawRequest(path: String, method: String, body: Data?) async throws -> Data {
        guard let url = URL(string: "\(AppConfiguration.apiBaseURL)\(path)") else {
            throw APIError.invalidURL(path)
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        guard let auth = await client.authService.currentSession() else {
            throw APIError.notAuthenticated
        }
        request.setValue(
            "Bearer \(auth.idToken)", forHTTPHeaderField: "Authorization"
        )
        if let body { request.httpBody = body }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIError.networkError("Invalid response")
        }
        if !(200...299).contains(http.statusCode) {
            throw APIError.httpError(
                statusCode: http.statusCode,
                body: String(data: data, encoding: .utf8) ?? ""
            )
        }
        return data
    }

    // MARK: - Decoder

    private static func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        let formatter = ISO8601DateFormatter()
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let str = try container.decode(String.self)
            guard let date = formatter.date(from: str) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Bad ISO8601 date: \(str)"
                )
            }
            return date
        }
        return d
    }
}
