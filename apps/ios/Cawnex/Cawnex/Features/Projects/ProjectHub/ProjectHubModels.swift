import SwiftUI

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

    var icon: String {
        switch type {
        case .vision: "eye"
        case .architecture: "layers"
        case .glossary: "book-open"
        case .design: "palette"
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

    var accentColor: Color {
        switch type {
        case .vision: Color(hex: 0x7C3AED)
        case .architecture: Color(hex: 0x3B82F6)
        case .glossary: Color(hex: 0x22C55E)
        case .design: Color(hex: 0xF97316)
        }
    }

    var chipColor: Color {
        switch status {
        case .draft: Color(hex: 0xF59E0B)
        case .notStarted: CawnexColors.mutedForeground
        case .inProgress: Color(hex: 0x3B82F6)
        case .complete: Color(hex: 0x22C55E)
        }
    }

    var chipBackground: Color {
        switch status {
        case .draft: Color(hex: 0xF59E0B).opacity(0.13)
        case .notStarted: CawnexColors.muted
        case .inProgress: Color(hex: 0x3B82F6).opacity(0.13)
        case .complete: Color(hex: 0x22C55E).opacity(0.13)
        }
    }

    var hasBorderAccent: Bool {
        status == .draft || status == .inProgress || status == .complete
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
    let dotColor: Color
}

struct ProjectHubDetail: Equatable {
    let project: Project
    let stats: ProjectStats
    let documents: [ProjectDocument]
    let backlog: BacklogSummary
    let murders: [MurderSummary]
}
