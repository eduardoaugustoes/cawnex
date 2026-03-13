import Foundation

@Observable
final class MVIDetailViewModel {
    private let mviService: any MVIService
    var state: ViewState<MVIBlackboardDetail> = .idle

    var detail: MVIBlackboardDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    init(mviService: any MVIService) {
        self.mviService = mviService
    }

    func load(projectId: String, mviId: String) async {
        state = .loading
        do {
            let loaded = try await mviService.getBlackboardDetail(projectId: projectId, mviId: mviId)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
