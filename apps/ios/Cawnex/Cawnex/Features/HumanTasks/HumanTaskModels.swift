import Foundation
import SwiftUI

enum HumanTaskStatus: String, CaseIterable {
    case pending
    case notified
    case inProgress = "in_progress"
    case responded
    case verifying
    case completed
    case verificationFailed = "verification_failed"
    case expired

    var displayName: String {
        switch self {
        case .pending: "Pending"
        case .notified: "Waiting for you"
        case .inProgress: "In progress"
        case .responded: "Submitted"
        case .verifying: "Verifying"
        case .completed: "Completed"
        case .verificationFailed: "Verification failed"
        case .expired: "Expired"
        }
    }

    var isActionable: Bool {
        self == .notified || self == .inProgress || self == .verificationFailed
    }
}

enum InputFieldType: String, CaseIterable {
    case string
    case text
    case secret
    case file
    case url
    case email
    case color
    case `enum`
    case boolean
    case number
}

struct InputField: Identifiable, Equatable {
    let id: String
    let type: InputFieldType
    let label: String
    let placeholder: String
    let description: String
    let required: Bool
    let pattern: String?
    let patternHint: String?
    let minLength: Int?
    let maxLength: Int?
    let accept: [String]
    let maxSizeMB: Int?
    let options: [EnumOption]
    let min: Double?
    let max: Double?

    struct EnumOption: Equatable {
        let value: String
        let label: String
    }
}

struct HumanTask: Identifiable, Equatable {
    let id: String
    let ask: String
    let subtype: String
    let status: HumanTaskStatus
    let deadlineHint: String
    let createdAt: String
}

struct HumanTaskDetail: Identifiable, Equatable {
    let id: String
    let ask: String
    let instructions: String
    let subtype: String
    let status: HumanTaskStatus
    let inputSchema: [InputField]
    let hasVerification: Bool
    let blocks: [String]
    let response: [String: String]?
    let steer: String?
    let deadlineHint: String
    let estimatedHumanHours: Double
    let createdAt: String
    let completedAt: String
}

struct HumanTaskListResponse: Equatable {
    let tasks: [String: [HumanTask]]
    let pendingCount: Int
    let totalCount: Int
}

struct UploadURLResponse: Equatable {
    let uploadUrl: String
    let assetKey: String
    let expiresIn: Int
}
