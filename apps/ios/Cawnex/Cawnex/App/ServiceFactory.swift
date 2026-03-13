import Foundation

struct ServiceFactory {
    let store: AppStore

    func makeProjectService() -> any ProjectService {
        InMemoryProjectService(store: store)
    }

    func makeProjectHubService() -> any ProjectHubService {
        InMemoryProjectHubService(store: store)
    }

    func makeBacklogService() -> any BacklogService {
        InMemoryBacklogService(store: store)
    }

    func makeMilestoneService() -> any MilestoneService {
        InMemoryMilestoneService(store: store)
    }

    func makeDocumentService() -> any DocumentService {
        InMemoryDocumentService()
    }

    func makeGoalService() -> any GoalService {
        InMemoryGoalService(store: store)
    }

    func makeMVIService() -> any MVIService {
        InMemoryMVIService(store: store)
    }

    func makeTaskService() -> any TaskService {
        InMemoryTaskService(store: store)
    }

    func makePRService() -> any PRService {
        InMemoryPRService(store: store)
    }

    func makeMurdersService() -> any MurdersService {
        InMemoryMurdersService(store: store)
    }

    func makeSkillsService() -> any SkillsService {
        InMemorySkillsService(store: store)
    }

    func makeCreditsService() -> any CreditsService {
        InMemoryCreditsService(store: store)
    }

    func makeNotificationService() -> any NotificationService {
        InMemoryNotificationService()
    }
}
