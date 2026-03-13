import Foundation

enum ActionStyle {
    case primary, secondary, destructive
}

struct StatusTransition<S: Hashable>: Identifiable {
    let id = UUID()
    let label: String
    let icon: String
    let target: S
    let style: ActionStyle
}
