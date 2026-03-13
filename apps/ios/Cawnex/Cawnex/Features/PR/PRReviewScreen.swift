import SwiftUI

struct PRReviewScreen: View {
    let projectId: String
    let prId: String
    @State var viewModel: PRReviewViewModel
    var onBack: () -> Void = {}

    var body: some View {
        ZStack(alignment: .bottom) {
            CawnexColors.background.ignoresSafeArea()

            VStack(spacing: 0) {
                navRow
                    .padding(.horizontal, CawnexSpacing.xl)

                ScrollView {
                    VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                        if case .loading = viewModel.state {
                            loadingView
                        }

                        if case .error(let message) = viewModel.state {
                            Text(message)
                                .font(CawnexTypography.caption)
                                .foregroundStyle(CawnexColors.destructive)
                        }

                        if let detail = viewModel.detail {
                            prHeaderCard(detail: detail)
                            verdictCard(verdict: detail.verdict)
                            planVsExecutionCard(steps: detail.planSteps)
                            askAICard(questions: detail.suggestedQuestions)
                            if !detail.conversation.isEmpty {
                                conversationSection(messages: detail.conversation)
                            }
                        }
                    }
                    .padding(.top, CawnexSpacing.md)
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.bottom, 220)
                }

                if let detail = viewModel.detail {
                    if !detail.conversation.isEmpty {
                        inputBar
                    }
                    actionBar(status: detail.status)
                }
            }
        }
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId, prId: prId) }
    }

    // MARK: - Nav

    private var navRow: some View {
        CawnexNavBar(title: "PR Review", onBack: onBack)
            .padding(.top, CawnexSpacing.sm)
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading PR review…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - PR Header Card

    private func prHeaderCard(detail: PRReviewDetail) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            // Title + Status
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
                    Text(detail.title)
                        .font(CawnexTypography.bodyBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text(detail.branch)
                        .font(CawnexTypography.mono)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                Text(detail.status.rawValue)
                    .font(CawnexTypography.label)
                    .foregroundStyle(detail.status.color)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(detail.status.color.opacity(0.13))
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.pill))
            }

            Divider().background(CawnexColors.border)

            // Breadcrumb
            HStack(spacing: 6) {
                Text(detail.breadcrumbMVI)
                    .font(CawnexTypography.footnoteMedium)
                    .foregroundStyle(CawnexColors.primaryLight)
                Image(systemName: "chevron.right")
                    .font(.system(size: 8))
                    .foregroundStyle(CawnexColors.mutedForeground)
                Text("Task: \(detail.breadcrumbTask)")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            // Meta Row
            HStack(spacing: CawnexSpacing.lg) {
                metaItem(icon: "dollarsign.circle", text: "\(detail.creditsCost) credits")
                metaItem(icon: "clock", text: "\(detail.aiMinutes) min")
                metaItem(icon: "doc", text: "\(detail.filesChanged) files")
                HStack(spacing: 4) {
                    Text("+\(detail.linesAdded)")
                        .font(CawnexTypography.mono)
                        .foregroundStyle(CawnexColors.success)
                    Text("-\(detail.linesRemoved)")
                        .font(CawnexTypography.mono)
                        .foregroundStyle(CawnexColors.destructive)
                }
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    private func metaItem(icon: String, text: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundStyle(CawnexColors.mutedForeground)
            Text(text)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - AI Verdict Card

    private func verdictCard(verdict: PRVerdict) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            // Verdict header
            HStack(spacing: CawnexSpacing.md) {
                Image(systemName: verdict.status.icon)
                    .font(.system(size: 18))
                    .foregroundStyle(verdict.status.color)
                    .frame(width: 36, height: 36)
                    .background(verdict.status.color.opacity(0.13))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text("\(verdict.crowName): \(verdict.status.rawValue)")
                        .font(CawnexTypography.subheading)
                        .foregroundStyle(verdict.status.color)
                    Text("\(verdict.confidence.rawValue) · \(verdict.filesAnalyzed) files analyzed")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }

            // Summary
            Text(verdict.summary)
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.cardForeground)
                .lineSpacing(4)

            Divider().background(CawnexColors.border)

            // Findings
            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("Key Findings")
                    .font(CawnexTypography.footnoteMedium)
                    .foregroundStyle(CawnexColors.mutedForeground)

                ForEach(verdict.findings) { finding in
                    HStack(alignment: .top, spacing: CawnexSpacing.sm) {
                        Image(systemName: finding.type.icon)
                            .font(.system(size: 14))
                            .foregroundStyle(finding.type.color)
                        Text(finding.text)
                            .font(CawnexTypography.footnote)
                            .foregroundStyle(CawnexColors.cardForeground)
                    }
                }
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.success.opacity(0.27), lineWidth: 1)
        )
    }

    // MARK: - Plan vs Execution

    private func planVsExecutionCard(steps: [PlanStep]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "arrow.triangle.branch")
                    .font(.system(size: 16))
                    .foregroundStyle(CawnexColors.primaryLight)
                Text("Plan vs Execution")
                    .font(CawnexTypography.subheading)
                    .foregroundStyle(CawnexColors.cardForeground)
            }

            ForEach(steps) { step in
                planStepView(step: step, index: steps.firstIndex(of: step)! + 1)
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    private func planStepView(step: PlanStep, index: Int) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            // Step header
            HStack(spacing: CawnexSpacing.sm) {
                Text("\(index)")
                    .font(CawnexTypography.microBold)
                    .foregroundStyle(.white)
                    .frame(width: 20, height: 20)
                    .background(step.badgeColor)
                    .clipShape(Circle())
                Text(step.crowName)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(CawnexColors.success)
            }

            // Plan block
            VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
                Text("Plan")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .tracking(0.8)
                Text(step.plan)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .lineSpacing(3)
            }
            .padding(.horizontal, CawnexSpacing.md)
            .padding(.vertical, CawnexSpacing.sm)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.background)
            .clipShape(RoundedRectangle(cornerRadius: 6))

            // Executed block
            VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
                Text("Executed")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(CawnexColors.success)
                    .tracking(0.8)
                Text(step.executed)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .lineSpacing(3)
            }
            .padding(.horizontal, CawnexSpacing.md)
            .padding(.vertical, CawnexSpacing.sm)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.success.opacity(0.05))
            .clipShape(RoundedRectangle(cornerRadius: 6))

            // Deviation hint
            if let hint = step.hint {
                HStack(alignment: .top, spacing: CawnexSpacing.sm) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(CawnexColors.warning)
                    Text(hint)
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.warning)
                        .lineSpacing(3)
                }
                .padding(.horizontal, CawnexSpacing.md)
                .padding(.vertical, CawnexSpacing.sm)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(CawnexColors.warning.opacity(0.07))
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(CawnexColors.warning.opacity(0.2), lineWidth: 1)
                )
            }
        }
    }

    // MARK: - Ask AI Card

    private func askAICard(questions: [String]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "sparkles")
                    .font(.system(size: 16))
                    .foregroundStyle(CawnexColors.primaryLight)
                Text("Ask about this PR")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.primaryLight)
            }

            FlowLayout(spacing: 6) {
                ForEach(questions, id: \.self) { question in
                    Button {
                        viewModel.messageText = question
                    } label: {
                        Text(question)
                            .font(CawnexTypography.footnote)
                            .foregroundStyle(CawnexColors.cardForeground)
                            .padding(.horizontal, CawnexSpacing.md)
                            .padding(.vertical, 6)
                            .background(CawnexColors.background)
                            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.pill))
                            .overlay(
                                RoundedRectangle(cornerRadius: CawnexRadius.pill)
                                    .stroke(CawnexColors.border, lineWidth: 1)
                            )
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.primaryLight, lineWidth: 1)
        )
    }

    // MARK: - Conversation

    private func conversationSection(messages: [PRChatMessage]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            ForEach(messages) { message in
                switch message.role {
                case .user:
                    userBubble(message.content)
                case .ai:
                    aiBubble(content: message.content, riskBadge: message.riskBadge)
                }
            }
        }
    }

    private func userBubble(_ text: String) -> some View {
        HStack {
            Spacer()
            Text(text)
                .font(CawnexTypography.caption)
                .foregroundStyle(.white)
                .lineSpacing(3)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(CawnexColors.primaryLight)
                .clipShape(
                    UnevenRoundedRectangle(
                        topLeadingRadius: 16,
                        bottomLeadingRadius: 16,
                        bottomTrailingRadius: 4,
                        topTrailingRadius: 16
                    )
                )
        }
    }

    private func aiBubble(content: String, riskBadge: String?) -> some View {
        HStack(alignment: .top, spacing: CawnexSpacing.md) {
            Image(systemName: "bird.fill")
                .font(.system(size: 14))
                .foregroundStyle(.white)
                .frame(width: 28, height: 28)
                .background(CawnexColors.primaryLight)
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                ForEach(content.components(separatedBy: "\n\n"), id: \.self) { paragraph in
                    Text(paragraph)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.cardForeground)
                        .lineSpacing(4)
                }

                if let badge = riskBadge {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark.shield.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(CawnexColors.success)
                        Text(badge)
                            .font(CawnexTypography.footnoteMedium)
                            .foregroundStyle(CawnexColors.success)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(CawnexColors.success.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(
                UnevenRoundedRectangle(
                    topLeadingRadius: 16,
                    bottomLeadingRadius: 4,
                    bottomTrailingRadius: 16,
                    topTrailingRadius: 16
                )
            )
            .overlay(
                UnevenRoundedRectangle(
                    topLeadingRadius: 16,
                    bottomLeadingRadius: 4,
                    bottomTrailingRadius: 16,
                    topTrailingRadius: 16
                )
                .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: CawnexSpacing.md) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "sparkles")
                    .font(.system(size: 14))
                    .foregroundStyle(CawnexColors.primaryLight)
                TextField("Ask anything about this PR...", text: $viewModel.messageText)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .tint(CawnexColors.primaryLight)
            }
            .padding(.horizontal, CawnexSpacing.lg)
            .frame(height: 40)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: 20))
            .overlay(
                RoundedRectangle(cornerRadius: 20)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )

            Button {} label: {
                Image(systemName: "arrow.up")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 36, height: 36)
                    .background(CawnexColors.primaryLight)
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, CawnexSpacing.xl)
        .padding(.vertical, CawnexSpacing.md)
    }

    // MARK: - Action Bar

    private func actionBar(status: PRStatus) -> some View {
        VStack(spacing: CawnexSpacing.sm) {
            // Primary: Approve & Merge
            Button {} label: {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: "arrow.triangle.merge")
                        .font(.system(size: 15, weight: .bold))
                    Text("Approve & Merge")
                        .font(CawnexTypography.sectionTitle)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(CawnexColors.success)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)

            // Secondary row
            HStack(spacing: CawnexSpacing.md) {
                secondaryButton(label: "Steer", icon: "arrow.uturn.left", color: CawnexColors.warning)
                secondaryButton(label: "Reject", icon: "xmark", color: CawnexColors.destructive)
                secondaryButton(label: "GitHub", icon: "arrow.up.right", color: CawnexColors.mutedForeground)
            }
        }
        .padding(.horizontal, CawnexSpacing.xl)
        .padding(.top, CawnexSpacing.lg)
        .padding(.bottom, 34)
        .background(CawnexColors.background)
    }

    private func secondaryButton(label: String, icon: String, color: Color) -> some View {
        Button {} label: {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 12, weight: .medium))
                Text(label)
                    .font(CawnexTypography.captionBold)
            }
            .foregroundStyle(color)
            .frame(maxWidth: .infinity)
            .frame(height: 40)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Flow Layout

private struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrange(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrange(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y), proposal: .unspecified)
        }
    }

    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, positions: [CGPoint]) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth, x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            positions.append(CGPoint(x: x, y: y))
            rowHeight = max(rowHeight, size.height)
            x += size.width + spacing
        }

        return (CGSize(width: maxWidth, height: y + rowHeight), positions)
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        PRReviewScreen(
            projectId: "1",
            prId: "pr15",
            viewModel: PRReviewViewModel(
                prService: InMemoryPRService(store: store)
            )
        )
    }
    .environment(store)
}
