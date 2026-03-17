import Foundation
import SwiftUI

@Observable
final class WaveExecutionViewModel {
    let waveService: any WaveService
    let projectId: String
    let waveId: String

    var detailState: ViewState<WaveDetail> = .idle
    var events: [WaveEvent] = []
    var isShipping: Set<String> = []
    var actionError: String?

    private var lastEventCursor: String?
    private var pollTimer: Timer?

    var detail: WaveDetail? {
        if case .loaded(let d) = detailState { return d }
        return nil
    }

    var wave: WaveSummary? { detail?.wave }
    var mvis: [WaveMVI] { detail?.mvis ?? [] }
    var humanTasks: [HumanTask] { detail?.humanTasks ?? [] }

    init(waveService: any WaveService, projectId: String, waveId: String) {
        self.waveService = waveService
        self.projectId = projectId
        self.waveId = waveId
    }

    // MARK: - Loading

    func load() async {
        detailState = .loading
        do {
            let loaded = try await waveService.getWave(projectId: projectId, waveId: waveId)
            detailState = .loaded(loaded)
            await loadEvents()
            startPolling()
        } catch {
            detailState = .error(error.localizedDescription)
        }
    }

    func loadEvents() async {
        do {
            let page = try await waveService.getEvents(
                projectId: projectId, waveId: waveId, after: lastEventCursor
            )
            if !page.events.isEmpty {
                // Prepend new events (newest first from API, we want chronological)
                let newEvents = page.events.reversed()
                for event in newEvents where !events.contains(where: { $0.id == event.id }) {
                    events.append(event)
                }
                lastEventCursor = page.events.first?.timestamp
            }
        } catch {
            // Silent — polling will retry
        }
    }

    // MARK: - Polling

    func startPolling() {
        stopPolling()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                await self.refresh()
            }
        }
    }

    func stopPolling() {
        pollTimer?.invalidate()
        pollTimer = nil
    }

    private func refresh() async {
        // Refresh wave detail
        if let loaded = try? await waveService.getWave(projectId: projectId, waveId: waveId) {
            detailState = .loaded(loaded)
            // Stop polling if wave is terminal
            if loaded.wave.status.isTerminal {
                stopPolling()
            }
        }
        // Fetch new events
        await loadEvents()
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
            // Refresh to get updated status
            await load()
        } catch {
            actionError = error.localizedDescription
        }
        isShipping.remove(mviId)
    }

    deinit {
        pollTimer?.invalidate()
    }
}
