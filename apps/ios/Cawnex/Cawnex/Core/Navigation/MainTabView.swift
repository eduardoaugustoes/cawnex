import SwiftUI

struct MainTabView: View {
    @Environment(AppStore.self) private var store
    var onSignOut: () -> Void = {}
    var apiClient: APIClient?
    @State private var selectedTab: CawnexTab = .projects
    @State private var tabRouter = TabRouter()
    @State private var isCreatingProject: Bool = false
    @State private var isCreatingMurder: Bool = false
    @State private var isCreatingSkill: Bool = false
    @State private var isShowingNotifications: Bool = false
    @State private var isShowingCredits: Bool = false
    @State private var isShowingAutopilot: Bool = false
    @State private var autopilotInitialMessage: String? = nil

    private var services: ServiceFactory {
        ServiceFactory(store: store, apiClient: apiClient)
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
                viewModel: DashboardViewModel(
                    projectService: services.makeProjectService()
                ),
                onBellTap: { isShowingNotifications = true },
                onAddTap: { isCreatingProject = true },
                onProjectTap: { project in
                    tabRouter.pushProject(project.id)
                },
                onAutopilotTap: {
                    autopilotInitialMessage = nil
                    isShowingAutopilot = true
                },
                onAutopilotVoice: { transcription in
                    autopilotInitialMessage = transcription
                    isShowingAutopilot = true
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
        .sheet(isPresented: $isShowingNotifications) {
            NavigationStack {
                NotificationsScreen(
                    viewModel: NotificationViewModel(
                        notificationService: services.makeNotificationService()
                    ),
                    onBack: { isShowingNotifications = false }
                )
            }
        }
        .sheet(isPresented: $isShowingAutopilot) {
            autopilotSheet
        }
    }

    // MARK: - Autopilot Sheet

    private var autopilotSheet: some View {
        let autopilotViewModel = AutopilotChatViewModel(
            autopilotService: services.makeAutopilotService()
        )
        let speechService = services.makeSpeechService()
        return NavigationStack {
            AutopilotChatScreen(
                viewModel: autopilotViewModel,
                speechService: speechService,
                initialMessage: autopilotInitialMessage,
                onCancel: { isShowingAutopilot = false },
                onPlanReview: { plan, sessionId in
                    tabRouter.projectPath.append(
                        ProjectRoute.autopilotPlanReview(plan: plan, sessionId: sessionId)
                    )
                    isShowingAutopilot = false
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
                ),
                onNewMurder: { isCreatingMurder = true }
            )
        }
        .sheet(isPresented: $isCreatingMurder) {
            CreateMurderScreen(
                viewModel: CreateMurderViewModel(),
                onCancel: { isCreatingMurder = false },
                onSave: { _ in isCreatingMurder = false }
            )
        }
    }

    private var skillsTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.skillPath) {
            SkillsScreen(
                viewModel: SkillsViewModel(
                    skillsService: services.makeSkillsService()
                ),
                onNewSkill: { isCreatingSkill = true }
            )
        }
        .sheet(isPresented: $isCreatingSkill) {
            CreateSkillScreen(
                viewModel: CreateSkillViewModel(),
                onCancel: { isCreatingSkill = false },
                onSave: { _ in isCreatingSkill = false }
            )
        }
    }

    private var settingsTab: some View {
        @Bindable var router = tabRouter
        return NavigationStack(path: $router.settingsPath) {
            SettingsScreen(
                onCreditsTap: { isShowingCredits = true },
                onSignOut: onSignOut
            )
            .navigationDestination(isPresented: $isShowingCredits) {
                CreditsScreen(
                    viewModel: CreditsViewModel(
                        creditsService: services.makeCreditsService()
                    ),
                    onBack: { isShowingCredits = false }
                )
            }
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
                onBacklogTap: { tabRouter.pushBacklog(projectId) },
                onHumanTasksTap: {
                    tabRouter.projectPath.append(ProjectRoute.humanTasks(projectId: projectId))
                },
                onWavesTap: {
                    tabRouter.projectPath.append(ProjectRoute.waves(projectId: projectId))
                }
            )
        case .document(let projectId, let type):
            documentDestination(projectId: projectId, type: type)
        case .backlog(let projectId):
            BacklogScreen(
                projectId: projectId,
                viewModel: BacklogViewModel(
                    backlogService: services.makeBacklogService()
                ),
                apiClient: apiClient,
                onBack: { tabRouter.projectPath.removeLast() },
                onGoalTap: { goalId in tabRouter.pushGoal(projectId, goalId: goalId) }
            )
        case .milestone(let projectId, let milestoneId):
            MilestoneDetailScreen(
                projectId: projectId,
                milestoneId: milestoneId,
                viewModel: MilestoneDetailViewModel(
                    milestoneService: services.makeMilestoneService()
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onGoalTap: { goalId in tabRouter.pushGoal(projectId, goalId: goalId) }
            )
        case .goal(let projectId, let goalId):
            GoalDetailScreen(
                projectId: projectId,
                goalId: goalId,
                viewModel: GoalDetailViewModel(
                    goalService: services.makeGoalService()
                ),
                apiClient: apiClient,
                onBack: { tabRouter.projectPath.removeLast() },
                onMVITap: { mviId in tabRouter.pushMVI(projectId, mviId: mviId) }
            )
        case .mvi(let projectId, let mviId, let waveId):
            MVIDetailScreen(
                projectId: projectId,
                waveId: waveId,
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
        case .humanTasks(let projectId):
            HumanTasksScreen(
                viewModel: HumanTaskViewModel(
                    humanTaskService: services.makeHumanTaskService(),
                    projectId: projectId
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onTaskTap: { taskId in
                    tabRouter.projectPath.append(
                        ProjectRoute.humanTaskDetail(projectId: projectId, humanTaskId: taskId)
                    )
                }
            )
        case .humanTaskDetail(let projectId, let humanTaskId):
            HumanTaskDetailScreen(
                viewModel: HumanTaskViewModel(
                    humanTaskService: services.makeHumanTaskService(),
                    projectId: projectId
                ),
                humanTaskId: humanTaskId,
                onBack: { tabRouter.projectPath.removeLast() }
            )
        case .waves(let projectId):
            WaveListScreen(
                viewModel: WaveListViewModel(
                    waveService: services.makeWaveService(),
                    projectId: projectId
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onLaunchWave: {
                    tabRouter.projectPath.append(ProjectRoute.waveLaunch(projectId: projectId))
                },
                onWaveTap: { waveId in
                    tabRouter.projectPath.append(
                        ProjectRoute.waveExecution(projectId: projectId, waveId: waveId)
                    )
                }
            )
        case .waveLaunch(let projectId):
            WaveLaunchScreen(
                viewModel: WaveLaunchViewModel(
                    backlogService: services.makeBacklogService(),
                    goalService: services.makeGoalService(),
                    waveService: services.makeWaveService(),
                    projectId: projectId
                ),
                onCancel: { tabRouter.projectPath.removeLast() },
                onLaunch: { wave in
                    tabRouter.projectPath.removeLast()
                    tabRouter.projectPath.append(
                        ProjectRoute.waveExecution(projectId: projectId, waveId: wave.id)
                    )
                }
            )
        case .waveExecution(let projectId, let waveId):
            WaveExecutionScreen(
                viewModel: WaveExecutionViewModel(
                    waveService: services.makeWaveService(),
                    projectId: projectId,
                    waveId: waveId
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onHumanTaskTap: { taskId in
                    tabRouter.projectPath.append(
                        ProjectRoute.humanTaskDetail(projectId: projectId, humanTaskId: taskId)
                    )
                },
                onMVITap: { mviId in
                    tabRouter.projectPath.append(
                        ProjectRoute.mvi(projectId: projectId, mviId: mviId, waveId: waveId)
                    )
                }
            )
        case .autopilotPlanReview(let plan, let sessionId):
            AutopilotPlanReviewScreen(
                plan: plan,
                sessionId: sessionId,
                viewModel: AutopilotChatViewModel(
                    autopilotService: services.makeAutopilotService()
                ),
                onBack: { tabRouter.projectPath.removeLast() },
                onLaunchComplete: { projectId, waveId in
                    tabRouter.popToRoot(tab: .projects)
                    tabRouter.projectPath.append(ProjectRoute.projectHub(projectId: projectId))
                    tabRouter.projectPath.append(
                        ProjectRoute.waveExecution(projectId: projectId, waveId: waveId)
                    )
                }
            )
        }
    }

    private func documentDestination(projectId: String, type: DocumentType) -> some View {
        DocumentScreen(
            projectId: projectId,
            type: type,
            viewModel: DocumentViewModel(
                documentService: services.makeDocumentService(projectId: projectId),
                documentType: type
            ),
            onBack: { tabRouter.projectPath.removeLast() }
        )
    }

}

#Preview {
    let store = AppStore()
    store.seedData()
    return MainTabView()
        .environment(store)
}
