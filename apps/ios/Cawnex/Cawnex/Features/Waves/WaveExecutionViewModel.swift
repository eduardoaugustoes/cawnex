import Foundation
import SwiftUI

@Observable
final class WaveExecutionViewModel {
    let waveService: any WaveService
    let streamService: any WaveEventStreamService
    let projectId: String
    let waveId: String

    var detailState: ViewState<WaveDetail> = .idle
    var events: [WaveEvent] = []
    var isShipping: Set<String> = []
    var actionError: String?
    /// Layer B: set when a `council_decision` SSE event arrives. The Wave
    /// Execution screen renders a tappable banner that deep-links to the
    /// Wave Review screen (S35).
    var pendingCouncilBanner: CouncilBanner?

    struct CouncilBanner: Identifiable, Equatable {
        var id: String { sessionId }
        let waveId: String
        let sessionId: String
        let decisionAction: String
        let confidence: Double
    }

    private var streamTask: Task<Void, Never>?

    var detail: WaveDetail? {
        if case .loaded(let d) = detailState { return d }
        return nil
    }

    var wave: WaveSummary? { detail?.wave }
    var mvis: [WaveMVI] { detail?.mvis ?? [] }
    var humanTasks: [HumanTask] { detail?.humanTasks ?? [] }

    init(
        waveService: any WaveService,
        streamService: any WaveEventStreamService,
        projectId: String,
        waveId: String
    ) {
        self.waveService = waveService
        self.streamService = streamService
        self.projectId = projectId
        self.waveId = waveId
    }

    // MARK: - Loading

    func load() async {
        detailState = .loading
        do {
            let loaded = try await waveService.getWave(projectId: projectId, waveId: waveId)
            detailState = .loaded(loaded)
            await loadInitialEvents()
            subscribe()
        } catch {
            detailState = .error(error.localizedDescription)
        }
    }

    /// Fetch any events that already exist for this wave (REST call). SSE
    /// only delivers events that arrive *after* connection; this catches
    /// the history. Once both have run, SSE takes over.
    private func loadInitialEvents() async {
        do {
            let page = try await waveService.getEvents(
                projectId: projectId, waveId: waveId, after: nil
            )
            let chronological = page.events.reversed()
            for event in chronological where !events.contains(where: { $0.id == event.id }) {
                events.append(event)
            }
        } catch {
            // Silent — SSE will pick up new events anyway.
        }
    }

    // MARK: - SSE subscription

    func subscribe() {
        unsubscribe()
        streamTask = Task { @MainActor [weak self] in
            guard let self else { return }
            let stream = self.streamService.subscribe(
                projectId: self.projectId, waveId: self.waveId
            )
            for await event in stream {
                self.append(event: event)
                await self.handleSideEffects(event: event)
            }
        }
    }

    func unsubscribe() {
        streamTask?.cancel()
        streamTask = nil
    }

    @MainActor
    private func append(event: WaveEvent) {
        guard !events.contains(where: { $0.id == event.id }) else { return }
        events.append(event)
    }

    /// Some events mutate aggregate state that SSE doesn't carry directly
    /// (wave status, MVI tasks_done counts). For those, refetch the wave
    /// detail. We deliberately do NOT refetch on every event — that would
    /// reintroduce the polling cost we're trying to remove.
    @MainActor
    private func handleSideEffects(event: WaveEvent) async {
        // Layer B: surface the Council banner on council_decision events.
        if event.eventType == "council_decision" {
            pendingCouncilBanner = CouncilBanner(
                waveId: event.extra["wave_id"] ?? waveId,
                sessionId: event.extra["session_id"] ?? "",
                decisionAction: event.extra["decision_action"] ?? "—",
                confidence: Double(event.extra["confidence"] ?? "") ?? 0
            )
            return
        }

        let triggersRefresh: Set<String> = [
            "mvi_ready", "mvi_shipped",
            "wave_paused", "wave_cancelled",
            "wave_activated", "wave_failed",
            "crow_completed", "crow_failed",
        ]
        guard triggersRefresh.contains(event.eventType) else { return }
        if let loaded = try? await waveService.getWave(
            projectId: projectId, waveId: waveId
        ) {
            detailState = .loaded(loaded)
            if loaded.wave.status.isTerminal {
                unsubscribe()
            }
        }
    }

    // MARK: - Actions

    func activate() async {
        actionError = nil
        do {
            _ = try await waveService.activateWave(projectId: projectId, waveId: waveId)
            await load()
        } catch {
            actionError = error.localizedDescription
        }
    }

    func pause() async {
        actionError = nil
        do {
            _ = try await waveService.pauseWave(projectId: projectId, waveId: waveId)
            await load()
        } catch {
            actionError = error.localizedDescription
        }
    }

    func cancel() async {
        actionError = nil
        do {
            _ = try await waveService.cancelWave(projectId: projectId, waveId: waveId)
            await load()
        } catch {
            actionError = error.localizedDescription
        }
    }

    func shipMVI(_ mviId: String) async {
        isShipping.insert(mviId)
        actionError = nil
        do {
            _ = try await waveService.shipMVI(projectId: projectId, waveId: waveId, mviId: mviId)
            await load()
        } catch {
            actionError = error.localizedDescription
        }
        isShipping.remove(mviId)
    }

    deinit {
        streamTask?.cancel()
    }
}
