import Foundation

@Observable
final class WaveListViewModel {
    let waveService: any WaveService
    let projectId: String
    var state: ViewState<[WaveSummary]> = .idle

    var waves: [WaveSummary] {
        if case .loaded(let w) = state { return w }
        return []
    }

    var activeWaves: [WaveSummary] { waves.filter { $0.status.isActive } }
    var completedWaves: [WaveSummary] { waves.filter { $0.status.isTerminal } }

    init(waveService: any WaveService, projectId: String) {
        self.waveService = waveService
        self.projectId = projectId
    }

    func load() async {
        state = .loading
        do {
            let loaded = try await waveService.listWaves(projectId: projectId)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
