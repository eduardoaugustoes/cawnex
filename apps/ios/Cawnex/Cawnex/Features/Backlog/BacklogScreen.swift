import SwiftUI

struct BacklogScreen: View {
    let projectId: String
    @State var viewModel: BacklogViewModel
    var apiClient: APIClient?
    var onBack: () -> Void = {}
    var onGoalTap: (String) -> Void = { _ in }

    @State private var isShowingPlanning = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                CawnexNavBar(
                    title: "Backlog",
                    onBack: onBack
                ) {
                    NavBarActionButton(icon: "plus", label: "Milestone") {
                        isShowingPlanning = true
                    }
                }

                switch viewModel.state {
                case .loading:
                    HStack {
                        Spacer()
                        ProgressView()
                            .tint(CawnexColors.primaryLight)
                        Spacer()
                    }
                    .padding(.vertical, CawnexSpacing.xxl)

                case .loaded(let milestones) where milestones.isEmpty:
                    VStack(spacing: CawnexSpacing.md) {
                        Image(systemName: "flag.2.crossed")
                            .font(.system(size: 36))
                            .foregroundStyle(CawnexColors.mutedForeground)
                        Text("No milestones yet")
                            .font(CawnexTypography.body)
                            .foregroundStyle(CawnexColors.mutedForeground)
                        Text("Tap + Milestone to plan your first one with AI")
                            .font(CawnexTypography.caption)
                            .foregroundStyle(CawnexColors.muted)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, CawnexSpacing.xxl)

                case .error(let message):
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                        .padding(.horizontal)

                default:
                    EmptyView()
                }

                ForEach(viewModel.milestones) { milestone in
                    MilestoneCard(
                        milestone: milestone,
                        isExpanded: viewModel.isExpanded(milestone.id),
                        onToggle: {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                viewModel.toggleExpanded(milestone.id)
                            }
                        },
                        onGoalTap: { goal in
                            onGoalTap(goal.id)
                        },
                        onEdit: {
                            // Edit via AI planning in future iteration
                        },
                        onStatusChange: { newStatus in
                            viewModel.milestoneStatusChanged(milestone.id, to: newStatus)
                        }
                    )
                }
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, CawnexSpacing.xl)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId) }
        .fullScreenCover(isPresented: $isShowingPlanning) {
            if let apiClient {
                MilestonePlanningScreen(
                    projectId: projectId,
                    planningService: APIMilestonePlanningService(
                        client: apiClient,
                        projectId: projectId
                    ),
                    onCancel: { isShowingPlanning = false },
                    onComplete: {
                        isShowingPlanning = false
                        Task { await viewModel.load(projectId: projectId) }
                    }
                )
            }
        }
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        BacklogScreen(
            projectId: "1",
            viewModel: BacklogViewModel(
                backlogService: InMemoryBacklogService(store: store)
            )
        )
    }
    .environment(store)
}
