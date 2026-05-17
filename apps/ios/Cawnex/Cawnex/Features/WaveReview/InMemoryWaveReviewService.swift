import Foundation

/// Seed-data implementation for previews + UI tests. Holds sessions in
/// memory keyed by sessionId; approve/reject mutate the local state.
final class InMemoryWaveReviewService: WaveReviewService {
    private var sessions: [String: CouncilSession] = [:]
    private(set) var approvedWaves: [String] = []
    private(set) var rejectedWaves: [(waveId: String, reason: String)] = []

    init(seed: [CouncilSession] = []) {
        for s in seed { sessions[s.sessionId] = s }
    }

    func fetchSession(
        projectId: String, sessionId: String
    ) async throws -> CouncilSession {
        guard let session = sessions[sessionId] else {
            throw WaveReviewError.notFound(sessionId: sessionId)
        }
        return session
    }

    func approveWave(projectId: String, waveId: String) async throws {
        approvedWaves.append(waveId)
    }

    func rejectWave(
        projectId: String, waveId: String, reason: String
    ) async throws {
        rejectedWaves.append((waveId, reason))
    }
}
