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
}
