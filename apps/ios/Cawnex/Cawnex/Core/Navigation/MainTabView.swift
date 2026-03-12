import SwiftUI

struct MainTabView: View {
    @Environment(AppStore.self) private var store
    @State private var selectedTab: CawnexTab = .projects
    @State private var tabRouter = TabRouter()

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                tabContent
                    .frame(maxHeight: .infinity)
            }

            VStack {
                Spacer()
                CawnexTabBar(selectedTab: $selectedTab)
            }
        }
        .environment(tabRouter)
    }

    @ViewBuilder
    private var tabContent: some View {
        switch selectedTab {
        case .projects:
            projectsTab
        case .murders:
            murdersTab
        case .skills:
            skillsTab
        case .settings:
            settingsTab
        }
    }

    // MARK: - Projects Tab

    private var projectsTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.projectPath) {
            DashboardScreen(
                userName: store.currentUser?.name ?? "",
                viewModel: DashboardViewModel(
                    projectService: InMemoryProjectService(store: store)
                ),
                onBellTap: {},
                onAddTap: {},
                onProjectTap: { project in
                    tabRouter.pushProject(project.id)
                }
            )
            .navigationDestination(for: ProjectRoute.self) { route in
                destinationView(for: route)
            }
        }
    }

    // MARK: - Other Tabs (placeholder stacks)

    private var murdersTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.murderPath) {
            tabPlaceholder("Murders")
        }
    }

    private var skillsTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.skillPath) {
            tabPlaceholder("Skills")
        }
    }

    private var settingsTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.settingsPath) {
            tabPlaceholder("Settings")
        }
    }

    // MARK: - Route Destinations

    @ViewBuilder
    private func destinationView(for route: ProjectRoute) -> some View {
        switch route {
        case .projectHub(let projectId):
            ProjectHubScreen(
                projectId: projectId,
                viewModel: ProjectHubViewModel(
                    projectHubService: InMemoryProjectHubService(store: store)
                )
            )
        case .document(let projectId, let type):
            routePlaceholder("Document: \(type.rawValue)", id: projectId)
        case .backlog(let projectId):
            BacklogScreen(
                projectId: projectId,
                viewModel: BacklogViewModel(
                    backlogService: InMemoryBacklogService(store: store)
                )
            )
        case .milestone(_, let milestoneId):
            routePlaceholder("Milestone", id: milestoneId)
        case .goal(_, let goalId):
            routePlaceholder("Goal", id: goalId)
        case .mvi(_, let mviId):
            routePlaceholder("MVI", id: mviId)
        case .task(_, let taskId):
            routePlaceholder("Task", id: taskId)
        case .pr(_, let prId):
            routePlaceholder("PR Review", id: prId)
        }
    }

    // MARK: - Placeholders

    private func tabPlaceholder(_ title: String) -> some View {
        VStack {
            Spacer()
            Text("\(title) — Coming Soon")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(CawnexColors.background)
    }

    private func routePlaceholder(_ title: String, id: String) -> some View {
        VStack {
            CawnexNavBar(title: title, onBack: {
                tabRouter.projectPath.removeLast()
            })
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.top, CawnexSpacing.sm)

            Spacer()
            VStack(spacing: CawnexSpacing.md) {
                Text(title)
                    .font(CawnexTypography.heading2)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text(id)
                    .font(CawnexTypography.mono)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return MainTabView()
        .environment(store)
}
