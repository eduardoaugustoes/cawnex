import Foundation

/// ProjectState represents the computed state of a project derived from its entities.
/// Decoded from the API response's `state` field in GET /projects/{id}.
struct ProjectState: Decodable {
    let crow_count: Int
    let mvi_queue_count: Int
    let wave_status: WaveStatus
    let council_decision: CouncilDecision?

    /// Crow completion count string (e.g., "12 of 15 Crows completed").
    var crowCompletionLabel: String {
        "\(crow_count) of \(crow_count) Crows completed"
    }

    /// MVI approval queue count string (e.g., "2 awaiting founder review").
    var mviQueueLabel: String {
        guard mvi_queue_count > 0 else { return "No items awaiting review" }
        return "\(mvi_queue_count) awaiting founder review"
    }

    /// Wave status label with elapsed time if running.
    var waveStatusLabel: String {
        wave_status.label
    }

    /// Council decision summary as a single-line callout (e.g., "Council: 4 approve, 1 security flag").
    var councilSummary: String? {
        guard let decision = council_decision else { return nil }
        return decision.summary
    }
}

/// WaveStatus represents the current wave execution state.
struct WaveStatus: Decodable {
    let status: String  // "running", "idle", "paused", etc.
    let elapsed_seconds: Int?  // Only present when running
    let started_at: String?  // ISO8601 timestamp

    /// Label for display (e.g., "Running • 2h 30m elapsed", "Idle").
    var label: String {
        switch status {
        case "running":
            if let elapsed = elapsed_seconds {
                return "Running • \(formatElapsedTime(elapsed))"
            }
            return "Running"
        case "paused":
            return "Paused"
        case "idle":
            return "Idle"
        default:
            return status.capitalized
        }
    }

    private func formatElapsedTime(_ seconds: Int) -> String {
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        if hours > 0 {
            return "\(hours)h \(minutes)m elapsed"
        }
        return "\(minutes)m elapsed"
    }
}

/// CouncilDecision represents the council's decision on the project.
struct CouncilDecision: Decodable {
    let approved_count: Int
    let security_flag_count: Int
    let other_count: Int

    /// Summary string for display (e.g., "Council: 4 approve, 1 security flag").
    var summary: String {
        var parts: [String] = []
        if approved_count > 0 {
            parts.append("\(approved_count) approve")
        }
        if security_flag_count > 0 {
            parts.append("\(security_flag_count) security flag")
        }
        if other_count > 0 {
            parts.append("\(other_count) other")
        }
        return "Council: " + parts.joined(separator: ", ")
    }
}
