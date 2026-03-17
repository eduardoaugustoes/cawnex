import Foundation

protocol WaveService {
    func listWaves(projectId: String) async throws -> [WaveSummary]
    func getWave(projectId: String, waveId: String) async throws -> WaveDetail
    func createWave(projectId: String, directive: String, goalId: String, mviIds: [String]) async throws -> CreateWaveResponse
    func activateWave(projectId: String, waveId: String) async throws -> WaveSummary
    func pauseWave(projectId: String, waveId: String) async throws -> WaveSummary
    func cancelWave(projectId: String, waveId: String) async throws -> WaveSummary
    func getEvents(projectId: String, waveId: String, after: String?) async throws -> WaveEventsPage
    func shipMVI(projectId: String, waveId: String, mviId: String) async throws -> String
}

final class InMemoryWaveService: WaveService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func listWaves(projectId: String) async throws -> [WaveSummary] {
        [
            WaveSummary(
                id: "w001",
                status: .executing,
                directive: "Build WhatsApp Business integration",
                progress: WaveProgress(mvisTotal: 3, mvisShipped: 1, tasksDone: 8, tasksTotal: 12),
                budget: WaveBudget(spent: 3_500_000, limit: 20_000_000),
                createdAt: "2026-03-16T10:00:00Z"
            ),
            WaveSummary(
                id: "w002",
                status: .delivered,
                directive: "Setup project foundation",
                progress: WaveProgress(mvisTotal: 2, mvisShipped: 2, tasksDone: 6, tasksTotal: 6),
                budget: WaveBudget(spent: 1_200_000, limit: 10_000_000),
                createdAt: "2026-03-14T10:00:00Z"
            ),
        ]
    }

    func getWave(projectId: String, waveId: String) async throws -> WaveDetail {
        WaveDetail(
            wave: WaveSummary(
                id: "w001",
                status: .executing,
                directive: "Build WhatsApp Business integration",
                progress: WaveProgress(mvisTotal: 3, mvisShipped: 1, tasksDone: 8, tasksTotal: 12),
                budget: WaveBudget(spent: 3_500_000, limit: 20_000_000),
                createdAt: "2026-03-16T10:00:00Z"
            ),
            mvis: [
                WaveMVI(id: "mvi-api", name: "WhatsApp API Setup", status: "ready_to_ship", description: "Configure webhook + message handling", tasksDone: 4, tasksTotal: 4, canShip: true, cost: 1_500_000),
                WaveMVI(id: "mvi-templates", name: "Message Templates", status: "executing", description: "Create and register templates", tasksDone: 2, tasksTotal: 4, canShip: false, cost: 800_000),
                WaveMVI(id: "mvi-dashboard", name: "Analytics Dashboard", status: "queued", description: "Build real-time metrics", tasksDone: 0, tasksTotal: 0, canShip: false, cost: 0),
            ],
            humanTasks: [
                HumanTask(id: "ht_token", ask: "Provide WhatsApp API token", subtype: "provide_secret", status: .notified, deadlineHint: "", createdAt: "2026-03-16T10:00:00Z"),
            ]
        )
    }

    func createWave(projectId: String, directive: String, goalId: String, mviIds: [String]) async throws -> CreateWaveResponse {
        CreateWaveResponse(waveId: "w003", status: "planning", mviIds: mviIds)
    }

    func activateWave(projectId: String, waveId: String) async throws -> WaveSummary {
        WaveSummary(
            id: waveId, status: .executing, directive: "Activated wave",
            progress: WaveProgress(mvisTotal: 2, mvisShipped: 0, tasksDone: 0, tasksTotal: 0),
            budget: WaveBudget(spent: 0, limit: 20_000_000),
            createdAt: "2026-03-17T10:00:00Z"
        )
    }

    func pauseWave(projectId: String, waveId: String) async throws -> WaveSummary {
        WaveSummary(
            id: waveId, status: .paused, directive: "Paused wave",
            progress: WaveProgress(mvisTotal: 2, mvisShipped: 0, tasksDone: 3, tasksTotal: 8),
            budget: WaveBudget(spent: 2_000_000, limit: 20_000_000),
            createdAt: "2026-03-17T10:00:00Z"
        )
    }

    func cancelWave(projectId: String, waveId: String) async throws -> WaveSummary {
        WaveSummary(
            id: waveId, status: .cancelled, directive: "Cancelled wave",
            progress: WaveProgress(mvisTotal: 2, mvisShipped: 0, tasksDone: 3, tasksTotal: 8),
            budget: WaveBudget(spent: 2_000_000, limit: 20_000_000),
            createdAt: "2026-03-17T10:00:00Z"
        )
    }

    func getEvents(projectId: String, waveId: String, after: String?) async throws -> WaveEventsPage {
        WaveEventsPage(
            events: [
                WaveEvent(id: "e1", eventType: "wave_activated", message: "Wave activated — 3 MVIs queued", color: "blue", timestamp: "2026-03-16T10:00:00Z", extra: [:]),
                WaveEvent(id: "e2", eventType: "worker_warming", message: "Execution engine warming up (~30s)", color: "yellow", timestamp: "2026-03-16T10:00:01Z", extra: [:]),
                WaveEvent(id: "e3", eventType: "worker_ready", message: "Engine ready — dispatching crows", color: "green", timestamp: "2026-03-16T10:00:35Z", extra: [:]),
                WaveEvent(id: "e4", eventType: "crow_assigned", message: "Murder assigned planner — plan", color: "purple", timestamp: "2026-03-16T10:00:36Z", extra: [:]),
                WaveEvent(id: "e5", eventType: "crow_completed", message: "Planner completed — 4 tasks identified", color: "green", timestamp: "2026-03-16T10:05:00Z", extra: [:]),
                WaveEvent(id: "e6", eventType: "human_task_created", message: "Human task created (provide_secret) — Provide WhatsApp API token", color: "orange", timestamp: "2026-03-16T10:05:01Z", extra: [:]),
                WaveEvent(id: "e7", eventType: "crow_assigned", message: "Murder assigned implementer — WhatsApp webhook setup", color: "purple", timestamp: "2026-03-16T10:05:02Z", extra: [:]),
            ],
            nextCursor: nil
        )
    }

    func shipMVI(projectId: String, waveId: String, mviId: String) async throws -> String {
        "shipped"
    }
}
