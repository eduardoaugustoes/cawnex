import Foundation

@Observable
final class CreateSkillViewModel {
    var name: String = ""
    var displayName: String = ""
    var icon: String = "bolt.fill"
    var category: SkillCategory = .dev
    var description: String = ""
    var tags: String = ""
    var isSubmitting: Bool = false
    var error: String?

    var canSubmit: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
    }

    func submit() async -> Skill? {
        guard canSubmit else { return nil }
        isSubmitting = true
        defer { isSubmitting = false }

        let resolvedDisplay = displayName.trimmingCharacters(in: .whitespaces).isEmpty
            ? name.trimmingCharacters(in: .whitespaces)
            : displayName.trimmingCharacters(in: .whitespaces)

        return Skill(
            id: UUID().uuidString,
            name: name.trimmingCharacters(in: .whitespaces),
            icon: icon,
            category: category,
            description: description.trimmingCharacters(in: .whitespaces),
            usedBy: "—",
            useCount: 0
        )
    }
}
