import Foundation

/// Parsed Server-Sent Event frame.
///
/// Backend emits `event: wave_event` with a JSON `data:` payload and an
/// `id:` field that's the DDB `SK` (ISO timestamp + `#event_type`).
/// Comment lines (`: keepalive`) are silently dropped by the decoder.
struct SSEFrame: Equatable {
    let id: String?
    let event: String?
    let data: String

    var isWaveEvent: Bool { event == "wave_event" }
}

/// Stateful line-based SSE decoder.
///
/// Consumers feed it lines from `URLSession.bytes(for:)`.lines and pull
/// completed frames as they arrive. Buffers accumulate across lines
/// until a blank line is seen, which dispatches the frame.
///
/// Single-event-loop only — not thread-safe by design (run inside one
/// `Task` per stream connection).
final class EventStreamDecoder {
    private var pendingId: String?
    private var pendingEvent: String?
    private var pendingData: [String] = []

    /// Process one line from the SSE stream. Returns a completed frame
    /// when the line is blank (end of an event), nil otherwise.
    func consume(line: String) -> SSEFrame? {
        // Comment line — by spec, lines starting with `:` are ignored.
        // Our backend uses `: keepalive` every 25s.
        if line.hasPrefix(":") {
            return nil
        }

        // Blank line — flush pending fields as a frame.
        if line.isEmpty {
            defer {
                pendingId = nil
                pendingEvent = nil
                pendingData = []
            }
            guard !pendingData.isEmpty else { return nil }
            return SSEFrame(
                id: pendingId,
                event: pendingEvent,
                data: pendingData.joined(separator: "\n")
            )
        }

        // Field line: `name: value` (per spec, missing colon = field name
        // with empty value, which we ignore — our backend always emits
        // `name: value`).
        guard let colonIndex = line.firstIndex(of: ":") else {
            return nil
        }
        let field = String(line[..<colonIndex])
        var valueStart = line.index(after: colonIndex)
        // SSE spec: if the first character after `:` is a space, skip it.
        if valueStart < line.endIndex, line[valueStart] == " " {
            valueStart = line.index(after: valueStart)
        }
        let value = String(line[valueStart...])

        switch field {
        case "id":
            pendingId = value
        case "event":
            pendingEvent = value
        case "data":
            pendingData.append(value)
        default:
            // Unknown field — spec says ignore. Our backend never emits
            // others (no `retry:`), so this is genuinely dead code path.
            break
        }
        return nil
    }
}
