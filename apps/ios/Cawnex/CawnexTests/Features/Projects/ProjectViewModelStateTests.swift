import Foundation
import Testing

@testable import Cawnex

// MARK: - ProjectViewModel State Decoding Tests

/// Snapshot tests verifying that ProjectViewModel correctly decodes and exposes
/// the projectState property for all ProjectStatus enum values.

struct ProjectViewModelStateTests {
    private func makeSUT(project: Project) -> (ProjectViewModel, InMemoryProjectService) {
        let store = AppStore()
        store.projects = [project]
        let service = InMemoryProjectService(store: store)
        let viewModel = ProjectViewModel(projectId: project.id, projectService: service)
        return (viewModel, service)
    }
    
    // MARK: - Draft State
    
    @Test @MainActor
    func projectState_decodesCorrectly_draft() async throws {
        let project = Project(
            id: "p-draft",
            name: "Draft Project",
            description: "A project in draft state",
            status: .draft,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0
        )
        let (viewModel, _) = makeSUT(project: project)
        
        await viewModel.load()
        
        #expect(viewModel.projectState == .draft)
        #expect(viewModel.project?.status == .draft)
    }
    
    // MARK: - Active State
    
    @Test @MainActor
    func projectState_decodesCorrectly_active() async throws {
        let project = Project(
            id: "p-active",
            name: "Active Project",
            description: "A project in active state",
            status: .active,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0
        )
        let (viewModel, _) = makeSUT(project: project)
        
        await viewModel.load()
        
        #expect(viewModel.projectState == .active)
        #expect(viewModel.project?.status == .active)
    }
    
    // MARK: - Running State
    
    @Test @MainActor
    func projectState_decodesCorrectly_running() async throws {
        let project = Project(
            id: "p-running",
            name: "Running Project",
            description: "A project in running state",
            status: .running,
            tasks: TaskCounts(done: 2, active: 3, refined: 1, draft: 0),
            creditsSpent: 100,
            humanEquivSaved: 500
        )
        let (viewModel, _) = makeSUT(project: project)
        
        await viewModel.load()
        
        #expect(viewModel.projectState == .running)
        #expect(viewModel.project?.status == .running)
        #expect(viewModel.project?.tasks.active == 3)
    }
    
    // MARK: - Idle State
    
    @Test @MainActor
    func projectState_decodesCorrectly_idle() async throws {
        let project = Project(
            id: "p-idle",
            name: "Idle Project",
            description: "A project in idle state",
            status: .idle,
            tasks: TaskCounts(done: 10, active: 0, refined: 5, draft: 2),
            creditsSpent: 250,
            humanEquivSaved: 1000
        )
        let (viewModel, _) = makeSUT(project: project)
        
        await viewModel.load()
        
        #expect(viewModel.projectState == .idle)
        #expect(viewModel.project?.status == .idle)
    }
    
    // MARK: - Completed State
    
    @Test @MainActor
    func projectState_decodesCorrectly_completed() async throws {
        let project = Project(
            id: "p-completed",
            name: "Completed Project",
            description: "A project in completed state",
            status: .completed,
            tasks: TaskCounts(done: 15, active: 0, refined: 0, draft: 0),
            creditsSpent: 500,
            humanEquivSaved: 2000
        )
        let (viewModel, _) = makeSUT(project: project)
        
        await viewModel.load()
        
        #expect(viewModel.projectState == .completed)
        #expect(viewModel.project?.status == .completed)
    }
    
    // MARK: - Published Property Updates
    
    @Test @MainActor
    func projectState_publishedProperty_updatesOnLoad() async throws {
        let project = Project(
            id: "p-test",
            name: "Test Project",
            description: "Test",
            status: .running,
            tasks: TaskCounts(done: 1, active: 1, refined: 0, draft: 0),
            creditsSpent: 50,
            humanEquivSaved: 250
        )
        let (viewModel, _) = makeSUT(project: project)
        
        // Initial state
        #expect(viewModel.projectState == .draft)
        
        // After load
        await viewModel.load()
        #expect(viewModel.projectState == .running)
    }
    
    // MARK: - State Loading Behavior
    
    @Test @MainActor
    func projectState_stateProperty_transitionsCorrectly() async throws {
        let project = Project(
            id: "p-state-test",
            name: "State Test",
            description: "Test",
            status: .active,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0
        )
        let (viewModel, _) = makeSUT(project: project)
        
        // Initial state is .idle
        if case .idle = viewModel.state {
            // Expected
        } else {
            #expect(false, "Initial state should be .idle")
        }
        
        // After load, state is .loaded
        await viewModel.load()
        if case .loaded(let loadedProject) = viewModel.state {
            #expect(loadedProject.status == .active)
        } else {
            #expect(false, "State should be .loaded after load()")
        }
    }
    
    // MARK: - All Enum Values Coverage
    
    @Test @MainActor
    func projectState_coversAllStatusEnumValues() async throws {
        let statuses: [ProjectStatus] = [.draft, .active, .running, .idle, .completed]
        
        for status in statuses {
            let project = Project(
                id: "p-\(status.rawValue)",
                name: "Project \(status.rawValue)",
                description: "Test",
                status: status,
                tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
                creditsSpent: 0,
                humanEquivSaved: 0
            )
            let (viewModel, _) = makeSUT(project: project)
            
            await viewModel.load()
            
            #expect(viewModel.projectState == status, "projectState should be \(status.rawValue)")
        }
    }
}
