import Foundation

@Observable
final class CreateMurderViewModel {
    var name: String = ""
    var murderType: MurderType = .dev
    var description: String = ""
    var isSubmitting: Bool = false
    var error: String?

    var canSubmit: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
            && !description.trimmingCharacters(in: .whitespaces).isEmpty
    }

    func submit() async -> Murder? {
        guard canSubmit else { return nil }
        isSubmitting = true
        defer { isSubmitting = false }
        return Murder(
            id: UUID().uuidString,
            name: name.trimmingCharacters(in: .whitespaces),
            type: murderType,
            description: description.trimmingCharacters(in: .whitespaces),
            status: .idle,
            icon: murderType.sfIcon,
            behaviorLines: [],
            crows: [],
            tasksDone: 0,
            successRate: 0,
            totalCost: 0
        )
    }
}
