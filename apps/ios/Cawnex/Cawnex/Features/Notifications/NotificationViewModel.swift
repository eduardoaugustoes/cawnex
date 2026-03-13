import Foundation

@Observable
final class NotificationViewModel {
    private let notificationService: any NotificationService

    var state: ViewState<NotificationsData> = .idle
    var selectedFilter: NotificationFilter = .all

    var data: NotificationsData? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    var filteredNeedsAction: [CawnexNotification] {
        guard let items = data?.needsAction else { return [] }
        switch selectedFilter {
        case .all, .needsAction: return items
        case .updates:           return []
        }
    }

    var filteredRecent: [CawnexNotification] {
        guard let items = data?.recent else { return [] }
        switch selectedFilter {
        case .all, .updates: return items
        case .needsAction:   return []
        }
    }

    var showNeedsActionSection: Bool { !filteredNeedsAction.isEmpty }
    var showRecentSection: Bool     { !filteredRecent.isEmpty }

    init(notificationService: any NotificationService) {
        self.notificationService = notificationService
    }

    func load() async {
        state = .loading
        do {
            let loaded = try await notificationService.getNotifications()
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    func selectFilter(_ filter: NotificationFilter) {
        selectedFilter = filter
    }
}
