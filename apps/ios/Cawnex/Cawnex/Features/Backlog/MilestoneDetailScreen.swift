import SwiftUI

struct MilestoneDetailScreen: View {
    let projectId: String
    let milestoneId: String
    @State var viewModel: MilestoneDetailViewModel
    var onBack: () -> Void = {}
    var onGoalTap: (String) -> Void = { _ in }

    var body: some View {
        VStack(spacing: 0) {
            scrollContent
            inputBar
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId, milestoneId: milestoneId) }
    }

    // MARK: - Scroll Content

    private var scrollContent: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                    navRow
                    if let detail = viewModel.detail {
                        definitionBanner
                        sectionsList(detail.sections)
                        chatArea(detail.messages)
                        previewButton
                        goalsSection(detail.goals)
                        addGoalButton
                    } else if case .loading = viewModel.state {
                        loadingView
                    } else if case .error(let message) = viewModel.state {
                        Text(message)
                            .font(CawnexTypography.caption)
                            .foregroundStyle(CawnexColors.destructive)
                    }
                }
                .padding(.top, CawnexSpacing.sm)
                .padding(.horizontal, CawnexSpacing.xl)
                .padding(.bottom, CawnexSpacing.xl)
                .id("bottom-anchor")
            }
            .onChange(of: viewModel.detail?.messages.count) {
                withAnimation {
                    proxy.scrollTo("bottom-anchor", anchor: .bottom)
                }
            }
        }
    }

    // MARK: - Nav Row

    private var navRow: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 10) {
                Button(action: onBack) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(CawnexColors.primaryLight)
                }
                .buttonStyle(.plain)

                if let detail = viewModel.detail {
                    Text(detail.milestone.name)
                        .font(CawnexTypography.heading3)
                        .foregroundStyle(CawnexColors.cardForeground)

                    StatusChip(milestoneStatus: detail.milestone.status)
                } else {
                    Text("Milestone")
                        .font(CawnexTypography.heading3)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
            }

            if let detail = viewModel.detail {
                Text(detail.breadcrumb)
                    .font(CawnexTypography.tiny)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
        }
    }

    // MARK: - Definition Banner

    @ViewBuilder
    private var definitionBanner: some View {
        DocPreviewBanner(
            title: "Milestone Definition",
            accentColor: CawnexColors.primary,
            sectionsComplete: viewModel.completedSections,
            sectionsTotal: viewModel.totalSections
        )
    }

    // MARK: - Sections List

    private func sectionsList(_ sections: [MilestoneDefinitionSection]) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("DEFINITION")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.5)
                .padding(.bottom, 2)

            VStack(spacing: 0) {
                ForEach(sections) { section in
                    sectionRow(section)
                }
            }
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    private func sectionRow(_ section: MilestoneDefinitionSection) -> some View {
        HStack(spacing: CawnexSpacing.sm) {
            Image(systemName: section.status == .complete ? "checkmark.circle.fill" : "circle")
                .font(.system(size: 16))
                .foregroundStyle(section.status == .complete ? CawnexColors.success : CawnexColors.mutedForeground)

            Text(section.title)
                .font(CawnexTypography.caption)
                .foregroundStyle(section.status == .complete ? CawnexColors.cardForeground : CawnexColors.mutedForeground)

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 12))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    // MARK: - Chat Area

    private func chatArea(_ messages: [ChatMessage]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            ForEach(messages) { message in
                ChatMessageBubble(message: message, accentColor: CawnexColors.primary)
            }
        }
    }

    // MARK: - Preview Button

    private var previewButton: some View {
        Button {} label: {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "eye")
                    .font(.system(size: 15))
                Text("Preview Milestone")
                    .font(CawnexTypography.subheading)
            }
            .foregroundStyle(CawnexColors.primary)
            .frame(maxWidth: .infinity)
            .frame(height: 40)
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.primary, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .disabled(true)
        .opacity(0.4)
    }

    // MARK: - Goals Section

    private func goalsSection(_ goals: [MilestoneGoalSummary]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            Text("GOALS")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.5)

            ForEach(goals) { goal in
                goalCard(goal)
            }
        }
    }

    private func goalCard(_ goal: MilestoneGoalSummary) -> some View {
        Button { onGoalTap(goal.id) } label: {
            VStack(alignment: .leading, spacing: 6) {
                // Top: name + status
                HStack {
                    Text(goal.name)
                        .font(CawnexTypography.captionBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Spacer()
                    Text(goal.status.label)
                        .font(CawnexTypography.tinyMedium)
                        .foregroundStyle(goal.status.color)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(goal.status.color.opacity(0.13))
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
                }

                // Description
                Text(goal.description)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)

                // Bottom: counts + view
                HStack {
                    Text("\(goal.mviCount) MVIs · \(goal.taskCount) tasks")
                        .font(CawnexTypography.tiny)
                        .foregroundStyle(CawnexColors.mutedForeground)
                    Spacer()
                    HStack(spacing: 4) {
                        Text("View")
                            .font(CawnexTypography.label)
                            .foregroundStyle(CawnexColors.primaryLight)
                        Image(systemName: "chevron.right")
                            .font(.system(size: 10))
                            .foregroundStyle(CawnexColors.primaryLight)
                    }
                }
            }
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Add Goal Button

    private var addGoalButton: some View {
        Button {} label: {
            HStack(spacing: 6) {
                Image(systemName: "plus")
                    .font(.system(size: 12))
                Text("Add Goal")
                    .font(CawnexTypography.footnoteMedium)
            }
            .foregroundStyle(CawnexColors.mutedForeground)
            .frame(maxWidth: .infinity)
            .frame(height: 38)
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .disabled(true)
        .opacity(0.4)
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading milestone…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        ChatInputBar(
            accentColor: CawnexColors.primary,
            text: $viewModel.messageText,
            onSend: {
                Task { await viewModel.sendMessage(projectId: projectId, milestoneId: milestoneId) }
            },
            isSending: viewModel.isSending
        )
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        MilestoneDetailScreen(
            projectId: "1",
            milestoneId: "ms1",
            viewModel: MilestoneDetailViewModel(
                milestoneService: InMemoryMilestoneService(store: store)
            )
        )
    }
    .environment(store)
}
