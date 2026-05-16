import Foundation

/// Two POST endpoints on the API for PR mutation: merge and reject.
///
/// Both routes return immediately after the GitHub call + DDB update;
/// the Murder reactor handles the wave-terminal transition async via
/// DDB Streams (no client polling needed for that).
protocol PRActionsService {
    func mergePR(
        projectId: String,
        waveId: String,
        mviId: String,
        prNumber: Int
    ) async throws -> MergeResult

    func rejectPR(
        projectId: String,
        waveId: String,
        mviId: String,
        prNumber: Int,
        reason: String
    ) async throws -> RejectResult
}

struct MergeResult: Decodable, Equatable {
    let merged: Bool
    let sha: String
    let mvi_status: String
    let wave_status: String
}

struct RejectResult: Decodable, Equatable {
    let rejected: Bool
    let mvi_status: String
}

final class APIPRActionsService: PRActionsService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func mergePR(
        projectId: String, waveId: String, mviId: String, prNumber: Int
    ) async throws -> MergeResult {
        struct Empty: Encodable {}
        return try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/mvis/\(mviId)/prs/\(prNumber)/merge",
            body: Empty()
        )
    }

    func rejectPR(
        projectId: String, waveId: String, mviId: String, prNumber: Int, reason: String
    ) async throws -> RejectResult {
        struct Body: Encodable {
            let reason: String
            let close_branch: Bool
        }
        return try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/mvis/\(mviId)/prs/\(prNumber)/reject",
            body: Body(reason: reason, close_branch: true)
        )
    }
}
