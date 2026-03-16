import Foundation

struct ServiceFactory {
    let store: AppStore
    let apiClient: APIClient?

    init(store: AppStore, apiClient: APIClient? = nil) {
        self.store = store
        self.apiClient = apiClient
    }

    func makeProjectService() -> any ProjectService {
        if let apiClient {
            return APIProjectService(client: apiClient, store: store)
        }
        return InMemoryProjectService(store: store)
    }

    func makeDocumentService(projectId: String = "") -> any DocumentService {
        if let apiClient, !projectId.isEmpty {
            return APIDocumentService(client: apiClient, projectId: projectId)
        }
        return InMemoryDocumentService()
    }

    func makeProjectHubService() -> any ProjectHubService {
        if let apiClient {
            return APIProjectHubService(client: apiClient, store: store)
        }
        return InMemoryProjectHubService(store: store)
    }

    func makeBacklogService() -> any BacklogService {
        if let apiClient {
            return APIBacklogService(client: apiClient)
        }
        return InMemoryBacklogService(store: store)
    }

    func makeMilestoneService() -> any MilestoneService {
        InMemoryMilestoneService(store: store)
    }

    func makeGoalService() -> any GoalService {
        if let apiClient {
            return APIGoalService(client: apiClient, store: store)
        }
        return InMemoryGoalService(store: store)
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
