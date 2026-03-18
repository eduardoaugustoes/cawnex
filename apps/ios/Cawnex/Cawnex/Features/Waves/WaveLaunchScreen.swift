import SwiftUI

struct WaveLaunchScreen: View {
    @State var viewModel: WaveLaunchViewModel
    var onCancel: () -> Void = {}
    var onLaunch: (WaveSummary) -> Void = { _ in }

    var body: some View {
        ZStack(alignment: .bottom) {
            CawnexColors.background.ignoresSafeArea()

            VStack(spacing: 0) {
                navRow
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.top, CawnexSpacing.lg)
                    .padding(.bottom, CawnexSpacing.md)

                ScrollView {
                    VStack(alignment: .leading, spacing: 28) {
                        heroSection
                        directiveField
                        goalPickerSection
                        if viewModel.selectedGoalId != nil {
                            mviSelectorSection
                        }
                    }
                    .padding(.top, CawnexSpacing.xxl)
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.bottom, 140)
                }
            }

            ctaBar
        }
        .task { await viewModel.loadGoals() }
    }

    // MARK: - Nav Row

    private var navRow: some View {
        HStack {
            Button("Cancel", action: onCancel)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)

            Spacer()

            Text("Launch Wave")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Text("Cancel")
                .font(CawnexTypography.body)
                .foregroundStyle(.clear)
        }
    }

    // MARK: - Hero

    private var heroSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("What should the crows build?")
                .font(CawnexTypography.heading1)
                .foregroundStyle(CawnexColors.cardForeground)

            Text("Define a directive, pick a goal and the MVIs\nto include in this execution wave.")
                .font(CawnexTypography.tagline)
                .foregroundStyle(CawnexColors.mutedForeground)
                .lineSpacing(6)
        }
    }

    // MARK: - Directive Field

    private var directiveField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("DIRECTIVE")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            TextField(
                "e.g. Build the WhatsApp Business integration end-to-end",
                text: $viewModel.directive,
                axis: .vertical
            )
            .font(CawnexTypography.body)
            .foregroundStyle(CawnexColors.cardForeground)
            .tint(CawnexColors.primaryLight)
            .lineLimit(3...6)
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )

            Text("What outcome should this wave deliver?")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Goal Picker

    private var goalPickerSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("GOAL")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            if viewModel.isLoadingGoals {
                HStack {
                    ProgressView().tint(CawnexColors.primary).scaleEffect(0.8)
                    Text("Loading goals...")
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                .frame(height: 48)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, CawnexSpacing.md)
                .background(CawnexColors.card)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CawnexRadius.md)
                        .stroke(CawnexColors.border, lineWidth: 1)
                )
            } else if viewModel.goals.isEmpty {
                Text("No goals found — create goals in the Backlog first")
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(height: 48)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, CawnexSpacing.md)
                    .background(CawnexColors.card)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(CawnexColors.border, lineWidth: 1)
                    )
            } else {
                VStack(spacing: CawnexSpacing.xs) {
                    ForEach(viewModel.goals) { goal in
                        goalRow(goal)
                    }
                }
            }
        }
    }

    private func goalRow(_ goal: Goal) -> some View {
        let isSelected = viewModel.selectedGoalId == goal.id
        return Button {
            Task { await viewModel.selectGoal(goal.id) }
        } label: {
            HStack(spacing: CawnexSpacing.md) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 18))
                    .foregroundStyle(isSelected ? CawnexColors.primary : CawnexColors.mutedForeground)

                VStack(alignment: .leading, spacing: 2) {
                    Text(goal.name)
                        .font(CawnexTypography.bodyBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text("\(goal.mviCount) MVIs · \(goal.mvisComplete) complete")
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }

                Spacer()

                Text(goal.status.label)
                    .font(CawnexTypography.tiny)
                    .foregroundStyle(goal.status.color)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(goal.status.color.opacity(0.15))
                    .clipShape(Capsule())
            }
            .padding(CawnexSpacing.md)
            .background(isSelected ? CawnexColors.primary.opacity(0.08) : CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(isSelected ? CawnexColors.primary.opacity(0.4) : CawnexColors.border, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - MVI Selector

    private var mviSelectorSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("MVIs TO INCLUDE")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            if viewModel.isLoadingMVIs {
                HStack {
                    ProgressView().tint(CawnexColors.primary).scaleEffect(0.8)
                    Text("Loading MVIs...")
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                .frame(height: 48)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, CawnexSpacing.md)
                .background(CawnexColors.card)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CawnexRadius.md)
                        .stroke(CawnexColors.border, lineWidth: 1)
                )
            } else if viewModel.mvIs.isEmpty {
                Text("No MVIs found for this goal")
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .padding(CawnexSpacing.md)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(CawnexColors.card)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(CawnexColors.border, lineWidth: 1)
                    )
            } else {
                VStack(spacing: CawnexSpacing.xs) {
                    ForEach(viewModel.mvIs) { mvi in
                        mviRow(mvi)
                    }
                }

                Text("Select the MVIs this wave should execute")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
        }
    }

    private func mviRow(_ mvi: MVI) -> some View {
        let isSelected = viewModel.selectedMVIIds.contains(mvi.id)
        return Button {
            viewModel.toggleMVI(mvi.id)
        } label: {
            HStack(spacing: CawnexSpacing.md) {
                Image(systemName: isSelected ? "checkmark.square.fill" : "square")
                    .font(.system(size: 18))
                    .foregroundStyle(isSelected ? CawnexColors.primaryLight : CawnexColors.mutedForeground)

                VStack(alignment: .leading, spacing: 2) {
                    Text(mvi.name)
                        .font(CawnexTypography.bodyBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    if !mvi.description.isEmpty {
                        Text(mvi.description)
                            .font(CawnexTypography.caption)
                            .foregroundStyle(CawnexColors.mutedForeground)
                            .lineLimit(1)
                    }
                }

                Spacer()

                Text(mvi.status.label)
                    .font(CawnexTypography.tiny)
                    .foregroundStyle(mvi.status.color)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(mvi.status.color.opacity(0.15))
                    .clipShape(Capsule())
            }
            .padding(CawnexSpacing.md)
            .background(isSelected ? CawnexColors.primaryLight.opacity(0.08) : CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(isSelected ? CawnexColors.primaryLight.opacity(0.4) : CawnexColors.border, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - CTA Bar

    private var ctaBar: some View {
        VStack(spacing: CawnexSpacing.md) {
            Button {
                Task {
                    if let summary = await viewModel.launch() {
                        onLaunch(summary)
                    }
                }
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.85)
                    } else {
                        Image(systemName: "bolt.fill")
                            .font(.system(size: 15, weight: .bold))
                    }
                    Text(viewModel.isSubmitting ? "Launching..." : "Launch Wave")
                        .font(CawnexTypography.sectionTitle)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(viewModel.canLaunch ? CawnexColors.primaryLight : CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)
            .disabled(!viewModel.canLaunch)

            if let error = viewModel.error {
                Text(error)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.destructive)
                    .multilineTextAlignment(.center)
            } else {
                Text("Crows will begin executing immediately after launch")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .multilineTextAlignment(.center)
            }
        }
        .padding(.horizontal, CawnexSpacing.xl)
        .padding(.top, CawnexSpacing.lg)
        .padding(.bottom, 34)
        .background(CawnexColors.background)
    }
}

// MARK: - Preview

#Preview {
    let store = AppStore()
    store.seedData()
    return WaveLaunchScreen(
        viewModel: WaveLaunchViewModel(
            backlogService: InMemoryBacklogService(store: store),
            goalService: InMemoryGoalService(store: store),
            waveService: InMemoryWaveService(store: store),
            projectId: "1"
        )
    )
}
