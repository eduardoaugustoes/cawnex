import Foundation

@Observable
final class CreditsViewModel {
    private let creditsService: any CreditsService
    var state: ViewState<CreditsData> = .idle

    var data: CreditsData? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    init(creditsService: any CreditsService) {
        self.creditsService = creditsService
    }

    func load() async {
        state = .loading
        do {
            let loaded = try await creditsService.getCreditsData()
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
