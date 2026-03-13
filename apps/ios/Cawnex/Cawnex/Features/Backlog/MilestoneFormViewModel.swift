import Foundation

@Observable
final class MilestoneFormViewModel {
    private let backlogService: any BacklogService
    private let projectId: String
    private let editingMilestone: Milestone?

    var name: String
    var description: String
    var isSubmitting: Bool = false
    var error: String?

    var isEditing: Bool { editingMilestone != nil }

    var canSubmit: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
            && !description.trimmingCharacters(in: .whitespaces).isEmpty
    }

    init(backlogService: any BacklogService, projectId: String, milestone: Milestone? = nil) {
        self.backlogService = backlogService
        self.projectId = projectId
        self.editingMilestone = milestone
        self.name = milestone?.name ?? ""
        self.description = milestone?.description ?? ""
    }

    func submit() async -> Milestone? {
        guard canSubmit else { return nil }
        isSubmitting = true
        defer { isSubmitting = false }
        do {
            if let existing = editingMilestone {
                return try await backlogService.updateMilestone(
                    projectId: projectId,
                    milestoneId: existing.id,
                    name: name.trimmingCharacters(in: .whitespaces),
                    description: description.trimmingCharacters(in: .whitespaces)
                )
            } else {
                return try await backlogService.createMilestone(
                    projectId: projectId,
                    name: name.trimmingCharacters(in: .whitespaces),
                    description: description.trimmingCharacters(in: .whitespaces)
                )
            }
        } catch {
            self.error = error.localizedDescription
            return nil
        }
    }
}
