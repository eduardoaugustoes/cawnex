import Foundation

struct ProjectStats: Equatable {
    let progress: Int
    let tasksDone: Int
    let tasksTotal: Int
    let pendingApprovals: Int
    let roi: Int
}

enum DocumentStatus: String, Equatable {
    case draft = "Draft"
    case notStarted = "Not started"
    case inProgress = "In progress"
    case complete = "Complete"
}

struct ProjectDocument: Identifiable, Equatable {
    let id: String
    let type: DocumentType
    let status: DocumentStatus

    var name: String {
        switch type {
        case .vision: "Vision"
        case .architecture: "Arch"
        case .glossary: "Glossary"
        case .design: "Design"
        }
    }

    var sfIcon: String {
        switch type {
        case .vision: "eye"
        case .architecture: "square.3.layers.3d"
        case .glossary: "book"
        case .design: "paintpalette"
        }
    }
}

struct BacklogSummary: Equatable {
    let pipeline: TaskCounts
    let activeMilestones: Int
    let mvisShipped: Int
    let mvisTotal: Int
}

struct MurderSummary: Identifiable, Equatable {
    let id: String
    let name: String
    let crowCount: Int
    let isActive: Bool
}

struct ProjectHubDetail: Equatable {
    let project: Project
    let stats: ProjectStats
    let documents: [ProjectDocument]
    let backlog: BacklogSummary
    let murders: [MurderSummary]
}
