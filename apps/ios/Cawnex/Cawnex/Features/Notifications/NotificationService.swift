import Foundation

// MARK: - Protocol

protocol NotificationService {
    func getNotifications() async throws -> NotificationsData
}

// MARK: - In-Memory Implementation

struct InMemoryNotificationService: NotificationService {

    func getNotifications() async throws -> NotificationsData {
        let needsAction: [CawnexNotification] = [
            CawnexNotification(
                id: "n1",
                type: .taskApproval,
                title: "Task ready for review",
                description: "Crow Dev-03 completed \"Set up authentication middleware\". Review the diff and approve to merge.",
                timestamp: "2m ago",
                isRead: false
            ),
            CawnexNotification(
                id: "n2",
                type: .mviReady,
                title: "MVI ready to ship",
                description: "MVI-04 \"Auth & Onboarding\" passed all checks. 8 tasks merged, merge checklist clear.",
                timestamp: "14m ago",
                isRead: false
            ),
            CawnexNotification(
                id: "n3",
                type: .taskFailed,
                title: "Task execution failed",
                description: "Crow Dev-01 hit a build error on \"Configure CI pipeline\". Retry count: 3/3.",
                timestamp: "38m ago",
                isRead: false
            ),
        ]

        let recent: [CawnexNotification] = [
            CawnexNotification(
                id: "n4",
                type: .mviShipped,
                title: "MVI shipped successfully",
                description: "MVI-03 \"Project Setup\" was shipped and deployed. 5 tasks, 0 regressions.",
                timestamp: "2h ago",
                isRead: true
            ),
            CawnexNotification(
                id: "n5",
                type: .creditsLow,
                title: "Credit balance low",
                description: "You have 42 credits remaining. Add more credits to keep your murders active.",
                timestamp: "3h ago",
                isRead: true
            ),
            CawnexNotification(
                id: "n6",
                type: .visionReady,
                title: "Vision document ready",
                description: "The Cawnex Vision document has been synthesized from your inputs and is ready to review.",
                timestamp: "5h ago",
                isRead: true
            ),
        ]

        return NotificationsData(needsAction: needsAction, recent: recent)
    }
}
