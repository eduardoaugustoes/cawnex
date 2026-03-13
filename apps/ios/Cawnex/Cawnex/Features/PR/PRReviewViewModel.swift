import Foundation

@Observable
final class PRReviewViewModel {
    private let prService: any PRService
    var state: ViewState<PRReviewDetail> = .idle
    var messageText: String = ""

    var detail: PRReviewDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    init(prService: any PRService) {
        self.prService = prService
    }

    func load(projectId: String, prId: String) async {
        state = .loading
        do {
            let loaded = try await prService.getPRReview(projectId: projectId, prId: prId)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
