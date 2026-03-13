import SwiftUI

struct MilestoneFormScreen: View {
    @State var viewModel: MilestoneFormViewModel
    var onCancel: () -> Void = {}
    var onSave: (Milestone) -> Void = { _ in }

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
                        nameField
                        descriptionField
                    }
                    .padding(.top, CawnexSpacing.xxl)
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.bottom, 140)
                }
            }

            ctaBar
        }
    }

    // MARK: - Nav Row

    private var navRow: some View {
        HStack {
            Button("Cancel", action: onCancel)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)

            Spacer()

            Text(viewModel.isEditing ? "Edit Milestone" : "New Milestone")
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
            Text(viewModel.isEditing ? "Refine this milestone" : "Define a milestone")
                .font(CawnexTypography.heading1)
                .foregroundStyle(CawnexColors.cardForeground)

            Text("Milestones are 3–6 month checkpoints that\ngroup related goals together.")
                .font(CawnexTypography.tagline)
                .foregroundStyle(CawnexColors.mutedForeground)
                .lineSpacing(6)
        }
    }

    // MARK: - Name Field

    private var nameField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("NAME")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            TextField("e.g. M1: Foundation", text: $viewModel.name)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)
                .tint(CawnexColors.primaryLight)
                .frame(height: 48)
                .padding(.horizontal, CawnexSpacing.md)
                .background(CawnexColors.card)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CawnexRadius.md)
                        .stroke(CawnexColors.border, lineWidth: 1)
                )
        }
    }

    // MARK: - Description Field

    private var descriptionField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("DESCRIPTION")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            TextField("What does achieving this milestone look like?", text: $viewModel.description, axis: .vertical)
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
        }
    }

    // MARK: - CTA Bar

    private var ctaBar: some View {
        VStack(spacing: CawnexSpacing.md) {
            Button {
                Task {
                    if let milestone = await viewModel.submit() {
                        onSave(milestone)
                    }
                }
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.85)
                    } else {
                        Image(systemName: viewModel.isEditing ? "checkmark" : "plus")
                            .font(.system(size: 15, weight: .bold))
                    }
                    Text(viewModel.isEditing ? "Save Changes" : "Create Milestone")
                        .font(CawnexTypography.sectionTitle)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(viewModel.canSubmit ? CawnexColors.primaryLight : CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)
            .disabled(!viewModel.canSubmit || viewModel.isSubmitting)

            if let error = viewModel.error {
                Text(error)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.destructive)
            } else {
                Text(viewModel.isEditing ? "Status changes happen from the backlog" : "Goals can be added after creation")
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

#Preview("Create") {
    let store = AppStore()
    store.seedData()
    return MilestoneFormScreen(
        viewModel: MilestoneFormViewModel(
            backlogService: InMemoryBacklogService(store: store),
            projectId: "1"
        )
    )
}

#Preview("Edit") {
    let store = AppStore()
    store.seedData()
    let milestone = Milestone(
        id: "ms1",
        name: "M1: Foundation",
        description: "Platform can accept, orchestrate, and deliver the first autonomous task end-to-end.",
        status: .active,
        tasks: TaskCounts(done: 8, active: 3, refined: 2, draft: 2),
        creditsSpent: 142,
        humanEquivSaved: 11000,
        roi: 78,
        goals: []
    )
    return MilestoneFormScreen(
        viewModel: MilestoneFormViewModel(
            backlogService: InMemoryBacklogService(store: store),
            projectId: "1",
            milestone: milestone
        )
    )
}
