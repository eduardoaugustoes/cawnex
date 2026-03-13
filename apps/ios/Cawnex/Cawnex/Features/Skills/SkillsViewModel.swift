import Foundation

@Observable
final class SkillsViewModel {
    private let skillsService: any SkillsService
    var state: ViewState<SkillsData> = .idle
    var selectedCategory: SkillCategory? = nil

    var data: SkillsData? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    var filteredSkills: [Skill] {
        guard let skills = data?.skills else { return [] }
        guard let category = selectedCategory else { return skills }
        return skills.filter { $0.category == category }
    }

    init(skillsService: any SkillsService) {
        self.skillsService = skillsService
    }

    func load() async {
        state = .loading
        do {
            let loaded = try await skillsService.getSkills()
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    func selectCategory(_ category: SkillCategory?) {
        selectedCategory = category
    }
}
