import Foundation

/// Long-lived SSE client backed by `URLSession.bytes(for:)`.
///
/// Opens an HTTPS connection to the stream service, attaches the current
/// Cognito JWT, parses SSE frames out of the byte stream, and exposes
/// them as an `AsyncStream<SSEFrame>`.
///
/// Reconnect: on any read error or non-2xx response, the client backs
/// off (1s, 2s, 5s, 10s, 10s, …) and reconnects, sending the last seen
/// frame `id` via the `Last-Event-ID` header so the server backfills the
/// gap. The caller cancels the connection by cancelling the surrounding
/// Task.
final class EventStreamClient: @unchecked Sendable {
    private let authService: any AuthService
    private let session: URLSession

    init(authService: any AuthService, session: URLSession? = nil) {
        self.authService = authService
        // Use a dedicated configuration with no timeout, so SSE connections
        // don't get killed by URLSession's default 60s timeoutIntervalForRequest.
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = .infinity
        cfg.timeoutIntervalForResource = .infinity
        cfg.httpAdditionalHeaders = ["Accept": "text/event-stream"]
        self.session = session ?? URLSession(configuration: cfg)
    }

    /// Open an SSE stream for a wave. Yields frames as they arrive.
    /// On cancellation, the underlying URL connection is torn down.
    func openWaveStream(projectId: String, waveId: String) -> AsyncStream<SSEFrame> {
        AsyncStream { continuation in
            let task = Task { [weak self] in
                guard let self else { return }
                var lastEventId: String?
                let backoff: [UInt64] = [
                    1_000_000_000, 2_000_000_000, 5_000_000_000,
                    10_000_000_000, 10_000_000_000,
                ]
                var attempt = 0
                while !Task.isCancelled {
                    do {
                        for try await frame in self.streamOnce(
                            projectId: projectId,
                            waveId: waveId,
                            lastEventId: lastEventId
                        ) {
                            attempt = 0
                            if let id = frame.id { lastEventId = id }
                            continuation.yield(frame)
                        }
                        // Server closed the stream cleanly — reconnect.
                    } catch is CancellationError {
                        break
                    } catch {
                        // Non-cancellation error: back off and retry.
                        #if DEBUG
                        print("[SSE] error: \(error). Reconnecting…")
                        #endif
                    }
                    if Task.isCancelled { break }
                    let delay = backoff[min(attempt, backoff.count - 1)]
                    attempt += 1
                    try? await Task.sleep(nanoseconds: delay)
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    /// One pass: open a connection, parse until it closes or errors.
    private func streamOnce(
        projectId: String,
        waveId: String,
        lastEventId: String?
    ) -> AsyncThrowingStream<SSEFrame, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let request = try await self.buildRequest(
                        projectId: projectId,
                        waveId: waveId,
                        lastEventId: lastEventId
                    )
                    let (bytes, response) = try await self.session.bytes(for: request)
                    guard let http = response as? HTTPURLResponse,
                        (200..<300).contains(http.statusCode)
                    else {
                        continuation.finish(
                            throwing: EventStreamError.httpStatus(
                                (response as? HTTPURLResponse)?.statusCode ?? -1
                            )
                        )
                        return
                    }

                    let decoder = EventStreamDecoder()
                    for try await line in bytes.lines {
                        if Task.isCancelled { break }
                        if let frame = decoder.consume(line: line) {
                            continuation.yield(frame)
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    private func buildRequest(
        projectId: String,
        waveId: String,
        lastEventId: String?
    ) async throws -> URLRequest {
        let urlString =
            "\(AppConfiguration.streamBaseURL)/projects/\(projectId)/waves/\(waveId)/stream"
        guard let url = URL(string: urlString) else {
            throw EventStreamError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
        if let lastEventId {
            request.setValue(lastEventId, forHTTPHeaderField: "Last-Event-ID")
        }
        guard let session = await authService.currentSession() else {
            throw EventStreamError.notAuthenticated
        }
        request.setValue("Bearer \(session.idToken)", forHTTPHeaderField: "Authorization")
        return request
    }
}

enum EventStreamError: Error, CustomStringConvertible {
    case invalidURL
    case notAuthenticated
    case httpStatus(Int)

    var description: String {
        switch self {
        case .invalidURL: "invalid stream URL"
        case .notAuthenticated: "not authenticated"
        case .httpStatus(let code): "HTTP \(code)"
        }
    }
}
