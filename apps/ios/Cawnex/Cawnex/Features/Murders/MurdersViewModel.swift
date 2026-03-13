import Foundation

@Observable
final class MurdersViewModel {
    private let murdersService: any MurdersService
    var state: ViewState<MurdersData> = .idle

    var data: MurdersData? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    init(murdersService: any MurdersService) {
        self.murdersService = murdersService
    }

    func load() async {
        state = .loading
        do {
            let loaded = try await murdersService.getMurders()
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
