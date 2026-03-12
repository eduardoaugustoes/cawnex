import Foundation

enum CawnexTab: String, CaseIterable, Equatable {
    case projects
    case murders
    case skills
    case settings

    var label: String {
        rawValue.uppercased()
    }

    var icon: String {
        switch self {
        case .projects: "folder"
        case .murders: "crow-icon"
        case .skills: "sparkles"
        case .settings: "gearshape"
        }
    }

    var isCustomIcon: Bool {
        self == .murders
    }

    var index: Int {
        CawnexTab.allCases.firstIndex(of: self) ?? 0
    }
}
