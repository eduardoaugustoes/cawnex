import Foundation

/// Contract for fetching Council sessions and triggering wave-level actions.
/// API and InMemory implementations both conform so views/ViewModels stay
/// swap-agnostic.
protocol WaveReviewService {
    /// Fetch the Council session for a wave. Always returns 200 on the
    /// backend regardless of session status; iOS branches on session.status.
    func fetchSession(
        projectId: String, sessionId: String
    ) async throws -> CouncilSession

    /// Approve the entire wave: flips status `under_human_review` -> `delivered`
    /// and merges every PR attached to a ready_to_ship MVI in the wave.
    func approveWave(projectId: String, waveId: String) async throws

    /// Reject the wave: maps to existing wave cancel + writes the reason
    /// to the wave's rework_reasons for the next planning pass.
    func rejectWave(
        projectId: String, waveId: String, reason: String
    ) async throws
}

enum WaveReviewError: Error, Equatable {
    case notFound(sessionId: String)
    case networkFailure(message: String)
    case approveFailed(detail: String)
    case rejectFailed(detail: String)
    case pollingTimeout
}
