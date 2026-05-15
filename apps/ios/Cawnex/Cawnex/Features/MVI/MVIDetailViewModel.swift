import Foundation

@Observable
final class MVIDetailViewModel {
    private let mviService: any MVIService
    private let streamService: any WaveEventStreamService

    var state: ViewState<MVIBlackboardDetail> = .idle

    var detail: MVIBlackboardDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    private var streamTask: Task<Void, Never>?
    private var resolvedWaveId: String?
    private var currentProjectId: String?
    private var currentMviId: String?

    init(
        mviService: any MVIService,
        streamService: any WaveEventStreamService
    ) {
        self.mviService = mviService
        self.streamService = streamService
    }

    func load(projectId: String, waveId: String?, mviId: String) async {
        state = .loading
        currentProjectId = projectId
        currentMviId = mviId
        do {
            let loaded = try await mviService.getBlackboardDetail(
                projectId: projectId, waveId: waveId, mviId: mviId
            )
            state = .loaded(loaded)
            // Extract resolved wave_id from the breadcrumb or from the
            // first live feed event. The breadcrumb is "Wave {id} › {name}".
            if let waveId {
                resolvedWaveId = waveId
            } else if let extractedId = Self.extractWaveId(fromBreadcrumb: loaded.breadcrumb) {
                resolvedWaveId = extractedId
            }
            subscribe()
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    // MARK: - SSE subscription

    func subscribe() {
        unsubscribe()
        guard let projectId = currentProjectId,
            let waveId = resolvedWaveId,
            let mviId = currentMviId
        else { return }

        streamTask = Task { @MainActor [weak self] in
            guard let self else { return }
            let stream = self.streamService.subscribe(projectId: projectId, waveId: waveId)
            for await event in stream {
                // Filter to events scoped to this MVI. wave-level events
                // (wave_activated, etc.) also surface here because the user
                // is on the MVI screen of *that* wave; gate by mvi_id when
                // present.
                let eventMviId = event.extra["mvi_id"] ?? ""
                if !eventMviId.isEmpty && eventMviId != mviId {
                    continue
                }
                self.refreshAfterEvent(event)
            }
        }
    }

    func unsubscribe() {
        streamTask?.cancel()
        streamTask = nil
    }

    @MainActor
    private func refreshAfterEvent(_ event: WaveEvent) {
        // Trigger a re-fetch of the blackboard on any matching event.
        // MVI detail aggregates from multiple sources (crows, events,
        // tasks_done), and we don't want to maintain a parallel mutation
        // path here. The fetch is cheap (one DDB query).
        guard let projectId = currentProjectId,
            let waveId = resolvedWaveId,
            let mviId = currentMviId
        else { return }
        Task { @MainActor [weak self] in
            guard let self else { return }
            if let loaded = try? await self.mviService.getBlackboardDetail(
                projectId: projectId, waveId: waveId, mviId: mviId
            ) {
                self.state = .loaded(loaded)
            }
        }
    }

    /// Pulls wave_id out of "Wave w1778... › Some MVI" breadcrumbs.
    private static func extractWaveId(fromBreadcrumb breadcrumb: String) -> String? {
        // Split on "›" if present, else on whitespace.
        let firstPart = breadcrumb.split(separator: "›").first.map(String.init) ?? breadcrumb
        let trimmed = firstPart.trimmingCharacters(in: .whitespaces)
        guard trimmed.lowercased().hasPrefix("wave ") else { return nil }
        let idPart = trimmed.dropFirst("wave ".count).trimmingCharacters(in: .whitespaces)
        return idPart.isEmpty ? nil : idPart
    }

    deinit {
        streamTask?.cancel()
    }
}
