import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: NotificationService

struct NotificationServiceContractTests {

    private func makeSUT() -> any NotificationService {
        InMemoryNotificationService()
    }

    @Test func getNotifications_returnsData() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        #expect(!data.all.isEmpty)
    }

    // MARK: - Needs Action

    @Test func getNotifications_needsActionNotEmpty() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        #expect(!data.needsAction.isEmpty)
    }

    @Test func getNotifications_needsActionIdsAreUnique() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        let ids = data.needsAction.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getNotifications_needsActionItemsHaveActionableTypes() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        let actionableTypes: Set<NotificationType> = [.taskApproval, .mviReady, .taskFailed]
        for notification in data.needsAction {
            #expect(actionableTypes.contains(notification.type))
        }
    }

    @Test func getNotifications_needsActionItemsHaveActions() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        for notification in data.needsAction {
            #expect(!notification.actions.isEmpty)
        }
    }

    // MARK: - Recent

    @Test func getNotifications_recentNotEmpty() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        #expect(!data.recent.isEmpty)
    }

    @Test func getNotifications_recentIdsAreUnique() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        let ids = data.recent.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getNotifications_recentItemsAreInfoTypes() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        let infoTypes: Set<NotificationType> = [.mviShipped, .creditsLow, .visionReady]
        for notification in data.recent {
            #expect(infoTypes.contains(notification.type))
        }
    }

    @Test func getNotifications_recentItemsHaveNoActions() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        for notification in data.recent {
            #expect(notification.actions.isEmpty)
        }
    }

    // MARK: - All Notifications

    @Test func getNotifications_allHaveRequiredFields() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        for notification in data.all {
            #expect(!notification.id.isEmpty)
            #expect(!notification.title.isEmpty)
            #expect(!notification.description.isEmpty)
            #expect(!notification.timestamp.isEmpty)
        }
    }

    @Test func getNotifications_allIdsAreGloballyUnique() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        let allIds = data.all.map(\.id)
        #expect(Set(allIds).count == allIds.count)
    }

    @Test func getNotifications_typeCategoryConsistency() async throws {
        let service = makeSUT()
        let data = try await service.getNotifications()
        for notification in data.needsAction {
            #expect(notification.type.category == .needsAction)
        }
        for notification in data.recent {
            #expect(notification.type.category == .updates)
        }
    }
}
