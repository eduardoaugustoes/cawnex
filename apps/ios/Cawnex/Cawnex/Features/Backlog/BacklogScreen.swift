import SwiftUI

struct BacklogScreen: View {
    let projectId: String
    @State var viewModel: BacklogViewModel
    var onBack: () -> Void = {}
    var onGoalTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                CawnexNavBar(
                    title: "Backlog",
                    onBack: onBack
                ) {
                    NavBarActionButton(icon: "plus", label: "Milestone")
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                        .padding(.horizontal)
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
