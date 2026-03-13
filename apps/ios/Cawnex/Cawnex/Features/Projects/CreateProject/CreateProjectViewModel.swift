import Foundation

@Observable
final class CreateProjectViewModel {
    private let projectService: any ProjectService

    var name: String = ""
    var oneLiner: String = ""
    var selectedMurders: Set<MurderType> = [.dev]
    var isSubmitting: Bool = false
    var error: String?

    var canCreate: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty && !selectedMurders.isEmpty
    }

    init(projectService: any ProjectService) {
        self.projectService = projectService
    }

    func toggleMurder(_ murder: MurderType) {
        if selectedMurders.contains(murder) {
            guard selectedMurders.count > 1 else { return }
            selectedMurders.remove(murder)
        } else {
            selectedMurders.insert(murder)
        }
    }

    func create() async -> Project? {
        guard canCreate else { return nil }
        isSubmitting = true
        defer { isSubmitting = false }
        do {
            return try await projectService.createProject(
                name: name.trimmingCharacters(in: .whitespaces),
                description: oneLiner.trimmingCharacters(in: .whitespaces),
                murders: selectedMurders
            )
        } catch {
            self.error = error.localizedDescription
            return nil
        }
    }
}
