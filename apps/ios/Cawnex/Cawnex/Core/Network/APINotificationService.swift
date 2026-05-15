import Foundation

/// Real backend implementation of NotificationService, replacing the
/// InMemory mock.
///
/// Endpoint: `GET /notifications`
///
/// The backend projects recent wave/crow events into a NotificationsData
/// payload. Approval gates (taskApproval) and credits_low / vision_ready
/// don't surface yet — those don't have event sources wired through the
/// events table.
final class APINotificationService: NotificationService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func getNotifications() async throws -> NotificationsData {
        let dto: NotificationsDataDTO = try await client.get("/notifications")
        return mapToNotificationsData(dto)
    }

    // MARK: - Mapping

    private func mapToNotificationsData(_ dto: NotificationsDataDTO) -> NotificationsData {
        NotificationsData(
            needsAction: dto.needs_action.map(mapNotification),
            recent: dto.recent.map(mapNotification)
        )
    }

    private func mapNotification(_ dto: NotificationDTO) -> CawnexNotification {
        CawnexNotification(
            id: dto.id,
            type: mapNotificationType(dto.type),
            title: dto.title,
            description: dto.description,
            timestamp: dto.timestamp,
            isRead: dto.is_read
        )
    }

    private func mapNotificationType(_ raw: String) -> NotificationType {
        NotificationType(rawValue: raw) ?? .mviReady
    }
}

// MARK: - DTOs

private struct NotificationsDataDTO: Decodable {
    let needs_action: [NotificationDTO]
    let recent: [NotificationDTO]
}

private struct NotificationDTO: Decodable {
    let id: String
    let type: String
    let title: String
    let description: String
    let timestamp: String
    let is_read: Bool
}
