import Foundation

// MARK: - Crow Draft

struct CrowDraft {
    let name: String
    let role: String
    let goal: String
    let description: String
}

// MARK: - ViewModel

@Observable
final class CreateCrowViewModel {

    // Functional fields
    var name: String = ""
    var role: String = ""
    var goal: String = ""
    var description: String = ""

    // Static preview fields (not bound to live controls)
    let modelName: String = "Claude Sonnet 4"
    let previewSkills: [String] = ["git-read", "git-write", "run-tests", "read-docs"]
    let backstoryPlaceholder: String = "e.g. You approach every task as a senior engineer who values clarity and minimal diff size…"
    let constraintsPlaceholder: String = "e.g. Never delete files. Never push directly to main. Never modify .env files."
    let isAdvancedExpanded: Bool = false

    var isSubmitting: Bool = false
    var error: String?

    var canSubmit: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
            && !role.trimmingCharacters(in: .whitespaces).isEmpty
            && !goal.trimmingCharacters(in: .whitespaces).isEmpty
    }

    func submit() -> CrowDraft? {
        guard canSubmit else { return nil }
        isSubmitting = true
        defer { isSubmitting = false }
        return CrowDraft(
            name: name.trimmingCharacters(in: .whitespaces),
            role: role.trimmingCharacters(in: .whitespaces),
            goal: goal.trimmingCharacters(in: .whitespaces),
            description: description.trimmingCharacters(in: .whitespaces)
        )
    }
}
