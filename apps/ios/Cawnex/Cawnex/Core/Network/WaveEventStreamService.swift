import Foundation

/// Domain-layer protocol for subscribing to a wave's live events.
///
/// Backed by `EventStreamClient` (SSE over HTTPS) in production, or an
/// in-memory stub for previews/tests.
protocol WaveEventStreamService {
    /// Open a stream of wave events. Caller cancels by cancelling the
    /// surrounding Task.
    func subscribe(projectId: String, waveId: String) -> AsyncStream<WaveEvent>
}

/// SSE-backed implementation that decodes JSON payloads into WaveEvent.
final class APIWaveEventStreamService: WaveEventStreamService, @unchecked Sendable {
    private let client: EventStreamClient

    init(client: EventStreamClient) {
        self.client = client
    }

    func subscribe(projectId: String, waveId: String) -> AsyncStream<WaveEvent> {
        AsyncStream { continuation in
            let task = Task {
                let frames = client.openWaveStream(projectId: projectId, waveId: waveId)
                for await frame in frames {
                    guard frame.isWaveEvent,
                        let event = Self.decode(frame: frame)
                    else { continue }
                    continuation.yield(event)
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    /// Decode the backend's SSE data payload into a WaveEvent.
    /// Payload shape (from apps/stream/src/stream/routes_pipe.py):
    ///   {
    ///     "event_type": "crow_assigned",
    ///     "message": "Implementer assigned",
    ///     "color": "blue",
    ///     "timestamp": "2026-05-15T19:14:12Z",
    ///     "wave_id": "w...",
    ///     "mvi_id": "m..."
    ///   }
    private static func decode(frame: SSEFrame) -> WaveEvent? {
        guard let data = frame.data.data(using: .utf8) else { return nil }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }

        // Use the SSE `id` (e.g., "2026-05-15T19:14:12Z#crow_assigned") if
        // present, otherwise synthesize from timestamp+event_type so
        // dedup still works for the rare server-omitted-id case.
        let id =
            frame.id
            ?? "\((json["timestamp"] as? String) ?? "")#\((json["event_type"] as? String) ?? "")"

        // Promote known keys into the extra map for downstream filtering
        // (notably mvi_id which MVI views key on).
        var extra: [String: String] = [:]
        for (key, value) in json {
            if let s = value as? String { extra[key] = s }
        }

        return WaveEvent(
            id: id,
            eventType: (json["event_type"] as? String) ?? "",
            message: (json["message"] as? String) ?? "",
            color: (json["color"] as? String) ?? "",
            timestamp: (json["timestamp"] as? String) ?? "",
            extra: extra
        )
    }
}

/// In-memory stub used by InMemory mode and previews. Yields nothing —
/// stream views just won't see live updates without the API client.
final class InMemoryWaveEventStreamService: WaveEventStreamService {
    func subscribe(projectId: String, waveId: String) -> AsyncStream<WaveEvent> {
        AsyncStream { continuation in
            continuation.finish()
        }
    }
}
