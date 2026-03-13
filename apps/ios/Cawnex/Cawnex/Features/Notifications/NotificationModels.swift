import Foundation

// MARK: - Notification Type

enum NotificationType: String, CaseIterable {
    case taskApproval = "task_approval"
    case mviReady = "mvi_ready"
    case taskFailed = "task_failed"
    case mviShipped = "mvi_shipped"
    case creditsLow = "credits_low"
    case visionReady = "vision_ready"

    var icon: String {
        switch self {
        case .taskApproval: return "checkmark.circle"
        case .mviReady:     return "shippingbox"
        case .taskFailed:   return "xmark.circle"
        case .mviShipped:   return "checkmark.seal.fill"
        case .creditsLow:   return "exclamationmark.triangle.fill"
        case .visionReady:  return "doc.text.fill"
        }
    }

    var category: NotificationCategory {
        switch self {
        case .taskApproval, .mviReady, .taskFailed: return .needsAction
        case .mviShipped, .creditsLow, .visionReady: return .updates
        }
    }
}

// MARK: - Notification Category

enum NotificationCategory: String, CaseIterable {
    case needsAction = "Needs Action"
    case updates = "Updates"
}

// MARK: - Notification Filter

enum NotificationFilter: Equatable {
    case all
    case needsAction
    case updates
}

// MARK: - Notification Action

enum NotificationAction: String {
    case approve = "Approve"
    case reject = "Reject"
    case review = "Review"
    case investigate = "Investigate"
}

// MARK: - Domain Model

struct CawnexNotification: Identifiable {
    let id: String
    let type: NotificationType
    let title: String
    let description: String
    let timestamp: String
    var isRead: Bool

    var actions: [NotificationAction] {
        switch type {
        case .taskApproval: return [.approve, .reject]
        case .mviReady:     return [.review]
        case .taskFailed:   return [.investigate]
        case .mviShipped, .creditsLow, .visionReady: return []
        }
    }
}

// MARK: - Aggregate

struct NotificationsData {
    let needsAction: [CawnexNotification]
    let recent: [CawnexNotification]

    var all: [CawnexNotification] { needsAction + recent }
}
