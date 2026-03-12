import SwiftUI

struct ProjectHubScreen: View {
    let projectId: String
    @State var viewModel: ProjectHubViewModel
    var onBack: () -> Void = {}
    var onDocumentTap: (DocumentType) -> Void = { _ in }
    var onBacklogTap: () -> Void = {}

    var body: some View {
        Group {
            switch viewModel.state {
            case .idle, .loading:
                ProgressView()
                    .tint(CawnexColors.primary)
            case .loaded(let detail):
                hubContent(detail)
            case .error(let message):
                Text(message)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.destructive)
                    .padding()
            }
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId) }
    }

    private func hubContent(_ detail: ProjectHubDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                CawnexNavBar(
                    title: detail.project.name,
                    backColor: CawnexColors.primary,
                    onBack: onBack
                ) {
                    NavBarIconButton(icon: "rectangle.grid.2x2")
                }

                projectHeader(detail.project)
                ProjectHubStatsRow(stats: detail.stats)
                ProjectHubDocumentsSection(documents: detail.documents, onDocumentTap: onDocumentTap)
                ProjectHubBacklogCard(backlog: detail.backlog, onTap: onBacklogTap)
                ProjectHubAgentsCard(murders: detail.murders)
                ProjectHubCostRow(project: detail.project, roi: detail.stats.roi)
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, CawnexSpacing.xl)
        }
    }

    private func projectHeader(_ project: Project) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(project.name)
                .font(.custom("Inter", size: 22).weight(.heavy))
                .foregroundStyle(CawnexColors.cardForeground)
            Text(project.description)
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        ProjectHubScreen(
            projectId: "1",
            viewModel: ProjectHubViewModel(
                projectHubService: InMemoryProjectHubService(store: store)
            )
        )
    }
    .environment(store)
}
