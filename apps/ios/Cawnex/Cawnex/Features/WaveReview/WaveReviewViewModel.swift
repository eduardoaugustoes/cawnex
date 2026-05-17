import Foundation
import Observation

@MainActor
@Observable
final class WaveReviewViewModel {
    enum State: Equatable {
        case idle
        case loading
        case loaded(CouncilSession)
        case actionPending(SubmittedAction)
        case actionSucceeded(SubmittedAction)
        case actionFailed(SubmittedAction, message: String)
        case error(message: String)
    }

    enum SubmittedAction: Equatable {
        case approved, rejected
    }

    var state: State = .idle

    private let service: WaveReviewService
    private var pollingTask: Task<Void, Never>?
    private let pollIntervalSeconds: UInt64 = 5
    private let pollTimeoutSeconds: TimeInterval = 300  // 5 min

    init(service: WaveReviewService) {
        self.service = service
    }

    // Polling task is cancelled explicitly via cancelPolling() when the
    // screen disappears; we don't cancel in deinit because pollingTask is
    // MainActor-isolated and deinit can run on any thread.

    func load(projectId: String, sessionId: String) async {
        state = .loading
        do {
            let session = try await service.fetchSession(
                projectId: projectId, sessionId: sessionId
            )
            state = .loaded(session)
            if session.status == .pending || session.status == .running {
                startPolling(projectId: projectId, sessionId: sessionId)
            }
        } catch WaveReviewError.notFound(let id) {
            state = .error(message: "Council session \(id) not found")
        } catch {
            state = .error(message: error.localizedDescription)
        }
    }

    func approve(projectId: String, waveId: String) async {
        state = .actionPending(.approved)
        do {
            try await service.approveWave(projectId: projectId, waveId: waveId)
            state = .actionSucceeded(.approved)
        } catch {
            state = .actionFailed(.approved, message: error.localizedDescription)
        }
    }

    func reject(projectId: String, waveId: String, reason: String) async {
        state = .actionPending(.rejected)
        do {
            try await service.rejectWave(
                projectId: projectId, waveId: waveId, reason: reason
            )
            state = .actionSucceeded(.rejected)
        } catch {
            state = .actionFailed(.rejected, message: error.localizedDescription)
        }
    }

    func cancelPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    // MARK: - Polling

    private func startPolling(projectId: String, sessionId: String) {
        pollingTask?.cancel()
        let start = Date()
        pollingTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                try? await Task.sleep(
                    nanoseconds: self.pollIntervalSeconds * 1_000_000_000
                )
                if Task.isCancelled { return }
                if Date().timeIntervalSince(start) > self.pollTimeoutSeconds {
                    self.state = .error(
                        message:
                            "Council pipeline appears stuck — founder must decide manually"
                    )
                    return
                }
                do {
                    let refreshed = try await self.service.fetchSession(
                        projectId: projectId, sessionId: sessionId
                    )
                    self.state = .loaded(refreshed)
                    if refreshed.status == .completed
                        || refreshed.status == .errored
                    {
                        return
                    }
                } catch {
                    // Transient errors don't kill the polling loop;
                    // the screen keeps the last-known state.
                }
            }
        }
    }
}
