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

    func makeGoalService() -> any GoalService {
        if let apiClient {
            return APIGoalService(client: apiClient, store: store)
        }
        return InMemoryGoalService(store: store)
    }

    func makeMVIService() -> any MVIService {
        if let apiClient {
            return APIMVIService(client: apiClient)
        }
        return InMemoryMVIService(store: store)
    }

    func makeMilestoneService() -> any MilestoneService {
        if let apiClient {
            return APIMilestoneService(client: apiClient)
        }
        return InMemoryMilestoneService(store: store)
    }

    func makeCreditsService() -> any CreditsService {
        if let apiClient {
            return APICreditsService(client: apiClient)
        }
        return InMemoryCreditsService(store: store)
    }

    func makeTaskService() -> any TaskService {
        if let apiClient {
            return APITaskService(client: apiClient)
        }
        return InMemoryTaskService(store: store)
    }

    func makePRService() -> any PRService {
        if let apiClient {
            return APIPRService(client: apiClient)
        }
        return InMemoryPRService(store: store)
    }

    func makeMurdersService() -> any MurdersService {
        if let apiClient {
            return APIMurdersService(client: apiClient)
        }
        return InMemoryMurdersService(store: store)
    }

    func makeSkillsService() -> any SkillsService {
        InMemorySkillsService(store: store)
    }

    func makeNotificationService() -> any NotificationService {
        if let apiClient {
            return APINotificationService(client: apiClient)
        }
        return InMemoryNotificationService()
    }

    func makeHumanTaskService() -> any HumanTaskService {
        if let apiClient {
            return APIHumanTaskService(client: apiClient)
        }
        return InMemoryHumanTaskService(store: store)
    }

    func makeWaveService() -> any WaveService {
        if let apiClient {
            return APIWaveService(client: apiClient)
        }
        return InMemoryWaveService(store: store)
    }

    func makeWaveEventStreamService() -> any WaveEventStreamService {
        if let apiClient {
            return APIWaveEventStreamService(
                client: EventStreamClient(authService: apiClient.authService)
            )
        }
        return InMemoryWaveEventStreamService()
    }

    func makeAutopilotService() -> any AutopilotService {
        if let apiClient {
            return APIAutopilotService(client: apiClient)
        }
        return InMemoryAutopilotService()
    }

    func makeSpeechService() -> SpeechService {
        SpeechService()
    }
}
