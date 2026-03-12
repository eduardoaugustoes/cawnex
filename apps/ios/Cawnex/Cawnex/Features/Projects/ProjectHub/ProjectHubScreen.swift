import SwiftUI

struct ProjectHubScreen: View {
    let projectId: String
    @State var viewModel: ProjectHubViewModel
    @Environment(TabRouter.self) private var tabRouter

    var body: some View {
        Group {
            if let detail = viewModel.detail {
                hubContent(detail)
            } else {
                ProgressView()
                    .tint(CawnexColors.primary)
            }
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId) }
    }

    // MARK: - Hub Content

    private func hubContent(_ detail: ProjectHubDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                CawnexNavBar(
                    title: detail.project.name,
                    backColor: CawnexColors.primary,
                    onBack: { tabRouter.popToRoot(tab: .projects) }
                ) {
                    NavBarIconButton(icon: "rectangle.grid.2x2")
                }

                projectHeader(detail.project)
                statsRow(detail.stats)
                documentsSection(detail.documents)
                backlogCard(detail.backlog)
                agentsCard(detail.murders)
                costRow(detail.project, roi: detail.stats.roi)
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, CawnexSpacing.xl)
        }
    }

    // MARK: - Project Header

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

    // MARK: - Stats Row

    private func statsRow(_ stats: ProjectStats) -> some View {
        HStack(spacing: 10) {
            statCard(value: "\(stats.progress)%", label: "Progress", color: CawnexColors.primary)
            statCard(value: "\(stats.tasksDone)/\(stats.tasksTotal)", label: "Tasks", color: CawnexColors.success)
            statCard(value: "\(stats.pendingApprovals)", label: "Pending", color: CawnexColors.warning)
            statCard(value: "\(stats.roi)x", label: "ROI", color: Color(hex: 0xF97316))
        }
    }

    private func statCard(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.custom("Inter", size: 20).weight(.heavy))
                .foregroundStyle(color)
            Text(label)
                .font(.custom("Inter", size: 11))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Documents Section

    private func documentsSection(_ documents: [ProjectDocument]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("DOCUMENTS")
                .font(.custom("Inter", size: 11).weight(.semibold))
                .tracking(1.5)
                .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: 10) {
                ForEach(documents) { doc in
                    documentCard(doc)
                }
            }
        }
    }

    private func documentCard(_ doc: ProjectDocument) -> some View {
        Button {
            tabRouter.pushDocument(projectId, type: doc.type)
        } label: {
            VStack(alignment: .leading, spacing: 6) {
                Image(systemName: doc.sfIcon)
                    .font(.system(size: 16))
                    .foregroundStyle(doc.hasBorderAccent ? doc.accentColor : CawnexColors.mutedForeground)
                    .frame(width: 20, height: 20)

                Text(doc.name)
                    .font(.custom("Inter", size: 13).weight(.semibold))
                    .foregroundStyle(CawnexColors.cardForeground)

                Text(doc.status.rawValue)
                    .font(.custom("Inter", size: 9).weight(.semibold))
                    .foregroundStyle(doc.chipColor)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(doc.chipBackground)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(
                        doc.hasBorderAccent ? doc.accentColor.opacity(0.27) : CawnexColors.border,
                        lineWidth: 1
                    )
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Backlog Card

    private func backlogCard(_ backlog: BacklogSummary) -> some View {
        Button {
            tabRouter.pushBacklog(projectId)
        } label: {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                HStack {
                    HStack(spacing: 10) {
                        Image(systemName: "target")
                            .font(.system(size: 18))
                            .foregroundStyle(CawnexColors.success)
                        Text("Backlog")
                            .font(.custom("Inter", size: 16).weight(.bold))
                            .foregroundStyle(CawnexColors.cardForeground)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 14))
                        .foregroundStyle(CawnexColors.mutedForeground)
                }

                backlogPipelineBar(backlog.pipeline)
                backlogLegend(backlog.pipeline)

                Text("\(backlog.activeMilestones) active · \(backlog.mvisShipped) of \(backlog.mvisTotal) MVIs shipped")
                    .font(.custom("Inter", size: 12))
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(CawnexSpacing.lg)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.success.opacity(0.27), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private func backlogPipelineBar(_ pipeline: TaskCounts) -> some View {
        GeometryReader { geometry in
            let total = pipeline.total
            let width = geometry.size.width
            HStack(spacing: 0) {
                if pipeline.done > 0 {
                    Rectangle()
                        .fill(CawnexColors.success)
                        .frame(width: total > 0 ? width * CGFloat(pipeline.done) / CGFloat(total) : 0)
                }
                if pipeline.active > 0 {
                    Rectangle()
                        .fill(CawnexColors.success.opacity(0.6))
                        .frame(width: total > 0 ? width * CGFloat(pipeline.active) / CGFloat(total) : 0)
                }
                if pipeline.refined > 0 {
                    Rectangle()
                        .fill(CawnexColors.success.opacity(0.33))
                        .frame(width: total > 0 ? width * CGFloat(pipeline.refined) / CGFloat(total) : 0)
                }
                if pipeline.draft > 0 {
                    Rectangle()
                        .fill(CawnexColors.success.opacity(0.13))
                }
            }
        }
        .frame(height: 8)
        .background(CawnexColors.success.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private func backlogLegend(_ pipeline: TaskCounts) -> some View {
        HStack(spacing: 6) {
            legendItem("\(pipeline.done) done", color: CawnexColors.success)
            legendItem("\(pipeline.active) active", color: CawnexColors.success.opacity(0.6))
            legendItem("\(pipeline.refined) refined", color: CawnexColors.success.opacity(0.33))
            legendItem("\(pipeline.draft) draft", color: CawnexColors.success.opacity(0.13))
        }
    }

    private func legendItem(_ text: String, color: Color) -> some View {
        HStack(spacing: 4) {
            RoundedRectangle(cornerRadius: 4)
                .fill(color)
                .frame(width: 8, height: 8)
            Text(text)
                .font(.custom("Inter", size: 11))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Agents Card

    private func agentsCard(_ murders: [MurderSummary]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack {
                HStack(spacing: 10) {
                    Image("crow-icon")
                        .renderingMode(.template)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: 20, height: 20)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text("Assigned Murders")
                        .font(.custom("Inter", size: 14).weight(.semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                Spacer()
                Text("Manage")
                    .font(.custom("Inter", size: 13).weight(.medium))
                    .foregroundStyle(CawnexColors.primary)
            }

            VStack(spacing: CawnexSpacing.sm) {
                ForEach(murders) { murder in
                    murderRow(murder)
                }
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    private func murderRow(_ murder: MurderSummary) -> some View {
        HStack {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(murder.dotColor)
                    .frame(width: 8, height: 8)
                Text(murder.name)
                    .font(.custom("Inter", size: 13).weight(.semibold))
                    .foregroundStyle(CawnexColors.cardForeground)
            }
            Spacer()
            Text("\(murder.crowCount) crows · \(murder.isActive ? "Active" : "Idle")")
                .font(.custom("Inter", size: 12))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Cost Row

    private func costRow(_ project: Project, roi: Int) -> some View {
        VStack(spacing: 10) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "wallet.bifold")
                        .font(.system(size: 14))
                        .foregroundStyle(CawnexColors.primary)
                    Text("This month")
                        .font(.custom("Inter", size: 12).weight(.medium))
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                Text("\(roi)x ROI")
                    .font(.custom("JetBrains Mono", size: 12).weight(.bold))
                    .foregroundStyle(Color(hex: 0xF97316))
            }

            BudgetBar(spent: project.creditsSpent, saved: project.humanEquivSaved)
        }
        .padding(.horizontal, CawnexSpacing.lg)
        .padding(.vertical, 14)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }
}

// MARK: - Preview

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
    .environment(TabRouter())
}
