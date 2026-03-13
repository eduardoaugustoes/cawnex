import SwiftUI

struct MainTabView: View {
    @Environment(AppStore.self) private var store
    @State private var selectedTab: CawnexTab = .projects
    @State private var tabRouter = TabRouter()
    @State private var isCreatingProject: Bool = false

    private var services: ServiceFactory {
        ServiceFactory(store: store)
    }

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                tabContent
                    .frame(maxHeight: .infinity)
            }

            if !tabRouter.isNavigatedDeep(tab: selectedTab) {
                VStack {
                    Spacer()
                    CawnexTabBar(selectedTab: $selectedTab)
                }
            }
        }
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
                    projectService: services.makeProjectService()
                ),
                onBellTap: {},
                onAddTap: { isCreatingProject = true },
                onProjectTap: { project in
                    tabRouter.pushProject(project.id)
                }
            )
            .navigationDestination(for: ProjectRoute.self) { route in
                destinationView(for: route)
            }
        }
        .sheet(isPresented: $isCreatingProject) {
            CreateProjectScreen(
                viewModel: CreateProjectViewModel(
                    projectService: services.makeProjectService()
                ),
                onCancel: { isCreatingProject = false },
                onCreate: { project in
                    isCreatingProject = false
                    tabRouter.pushProject(project.id)
                }
            )
        }
    }

    // MARK: - Other Tabs (placeholder stacks)

    private var murdersTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.murderPath) {
            MurdersScreen(
                viewModel: MurdersViewModel(
                    murdersService: services.makeMurdersService()
                )
            )
        }
    }

    private var skillsTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.skillPath) {
            SkillsScreen(
                viewModel: SkillsViewModel(
                    skillsService: services.makeSkillsService()
                )
            )
        }
    }

    private var settingsTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.settingsPath) {
            SettingsScreen()
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
                    projectHubService: services.makeProjectHubService()
                ),
                onBack: { tabRouter.popToRoot(tab: .projects) },
                onDocumentTap: { type in tabRouter.pushDocument(projectId, type: type) },
                onBacklogTap: { tabRouter.pushBacklog(projectId) }
            )
        case .document(let projectId, let type):
            documentDestination(projectId: projectId, type: type)
        case .backlog(let projectId):
            BacklogScreen(
                projectId: projectId,
                viewModel: BacklogViewModel(
                    backlogService: services.makeBacklogService()
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onGoalTap: { goalId in tabRouter.pushGoal(projectId, goalId: goalId) }
            )
        case .milestone(_, let milestoneId):
            routePlaceholder("Milestone", id: milestoneId)
        case .goal(let projectId, let goalId):
            GoalDetailScreen(
                projectId: projectId,
                goalId: goalId,
                viewModel: GoalDetailViewModel(
                    goalService: services.makeGoalService()
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onMVITap: { mviId in tabRouter.pushMVI(projectId, mviId: mviId) }
            )
        case .mvi(let projectId, let mviId):
            MVIDetailScreen(
                projectId: projectId,
                mviId: mviId,
                viewModel: MVIDetailViewModel(
                    mviService: services.makeMVIService()
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onTaskTap: { taskId in tabRouter.pushTask(projectId, taskId: taskId) },
                onPRTap: { prId in tabRouter.pushPR(projectId, prId: prId) }
            )
        case .task(let projectId, let taskId):
            TaskDetailScreen(
                projectId: projectId,
                taskId: taskId,
                viewModel: TaskDetailViewModel(
                    taskService: services.makeTaskService()
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onPRTap: { prId in tabRouter.pushPR(projectId, prId: prId) }
            )
        case .pr(let projectId, let prId):
            PRReviewScreen(
                projectId: projectId,
                prId: prId,
                viewModel: PRReviewViewModel(
                    prService: services.makePRService()
                ),
                onBack: { tabRouter.projectPath.removeLast() }
            )
        }
    }

    private func documentDestination(projectId: String, type: DocumentType) -> some View {
        DocumentScreen(
            projectId: projectId,
            type: type,
            viewModel: DocumentViewModel(
                documentService: services.makeDocumentService(),
                documentType: type
            ),
            onBack: { tabRouter.projectPath.removeLast() }
        )
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
