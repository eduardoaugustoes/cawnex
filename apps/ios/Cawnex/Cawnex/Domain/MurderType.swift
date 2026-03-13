import Foundation

enum MurderType: String, CaseIterable, Identifiable {
    case dev
    case editorial
    case infra
    case data
    case social

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .dev: return "Dev"
        case .editorial: return "Editorial"
        case .infra: return "Infra"
        case .data: return "Data"
        case .social: return "Social"
        }
    }

    var sfIcon: String {
        switch self {
        case .dev: return "curlybraces"
        case .editorial: return "pencil"
        case .infra: return "server.rack"
        case .data: return "externaldrive"
        case .social: return "square.and.arrow.up"
        }
    }
}
