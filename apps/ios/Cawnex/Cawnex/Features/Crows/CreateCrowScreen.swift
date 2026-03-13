import SwiftUI

struct CreateCrowScreen: View {
    @State var viewModel: CreateCrowViewModel
    var onCancel: () -> Void = {}
    var onSave: (CrowDraft) -> Void = { _ in }

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
                        identitySection
                        modelSection
                        descriptionSection
                        skillsSection
                        backstorySection
                        constraintsSection
                        advancedSection
                    }
                    .padding(.top, CawnexSpacing.xl)
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.bottom, 40)
                }
            }
        }
    }

    // MARK: - Nav Row

    private var navRow: some View {
        HStack {
            Button("Cancel", action: onCancel)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)
                .buttonStyle(.plain)

            Spacer()

            Text("New Crow")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Button {
                if let draft = viewModel.submit() {
                    onSave(draft)
                }
            } label: {
                Text("Save")
                    .font(CawnexTypography.bodyBold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, CawnexSpacing.md)
                    .padding(.vertical, 6)
                    .background(viewModel.canSubmit ? CawnexColors.primaryLight : CawnexColors.muted)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)
            .disabled(!viewModel.canSubmit)
        }
    }

    // MARK: - Identity Section

    private var identitySection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionLabel("IDENTITY")

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                inputField(
                    label: "Name",
                    placeholder: "e.g. Planner Crow",
                    text: $viewModel.name
                )
                inputField(
                    label: "Role",
                    placeholder: "e.g. Planner / Implementer / Reviewer",
                    text: $viewModel.role
                )
                inputField(
                    label: "Goal",
                    placeholder: "e.g. Break down goals into executable tasks",
                    text: $viewModel.goal
                )
            }
        }
    }

    // MARK: - Model Section

    private var modelSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionLabel("MODEL")

            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(viewModel.modelName)
                        .font(CawnexTypography.bodyBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text("Choose based on task complexity and cost")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                Image(systemName: "chevron.down")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
            .disabled(true)
            .opacity(0.4)
        }
    }

    // MARK: - Description Section

    private var descriptionSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionLabel("DESCRIPTION")

            TextField(
                "The Murder reads this to decide when to deploy this crow",
                text: $viewModel.description,
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
        }
    }

    // MARK: - Skills Section

    private var skillsSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionLabel("SKILLS")

            Text("What capabilities does this crow have?")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: CawnexSpacing.sm) {
                    ForEach(viewModel.previewSkills, id: \.self) { skill in
                        skillChip(skill)
                    }
                    skillChip("+ add skill", isAddButton: true)
                }
            }
            .disabled(true)
            .opacity(0.4)
        }
    }

    private func skillChip(_ label: String, isAddButton: Bool = false) -> some View {
        Text(label)
            .font(CawnexTypography.captionMedium)
            .foregroundStyle(isAddButton ? CawnexColors.primaryLight : CawnexColors.cardForeground)
            .padding(.horizontal, CawnexSpacing.md)
            .padding(.vertical, 6)
            .background(isAddButton ? CawnexColors.primaryLight.opacity(0.12) : CawnexColors.muted)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.pill))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.pill)
                    .stroke(
                        isAddButton ? CawnexColors.primaryLight.opacity(0.3) : Color.clear,
                        lineWidth: 1
                    )
            )
    }

    // MARK: - Backstory Section

    private var backstorySection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionLabel("BACKSTORY")

            Text(viewModel.backstoryPlaceholder)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)
                .lineLimit(3...6)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(CawnexSpacing.md)
                .background(CawnexColors.card)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CawnexRadius.md)
                        .stroke(CawnexColors.border, lineWidth: 1)
                )
                .disabled(true)
                .opacity(0.4)

            Text("Shapes how this crow approaches problems and makes decisions")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Constraints Section

    private var constraintsSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionLabel("CONSTRAINTS")

            Text(viewModel.constraintsPlaceholder)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.destructive.opacity(0.7))
                .lineLimit(3...6)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(CawnexSpacing.md)
                .background(CawnexColors.destructive.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CawnexRadius.md)
                        .stroke(CawnexColors.destructive.opacity(0.35), lineWidth: 1)
                )
                .disabled(true)
                .opacity(0.4)

            HStack(spacing: CawnexSpacing.xs) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 11))
                    .foregroundStyle(CawnexColors.destructive)
                Text("Hard boundaries — these override all other instructions")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.destructive)
            }
        }
    }

    // MARK: - Advanced Section

    private var advancedSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack {
                sectionLabel("ADVANCED")
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .rotationEffect(.degrees(viewModel.isAdvancedExpanded ? 90 : 0))
            }

            HStack(spacing: CawnexSpacing.md) {
                advancedRow(icon: "slider.horizontal.3", label: "Temperature", value: "0.7")
                Spacer()
                advancedRow(icon: "arrow.triangle.2.circlepath", label: "Max retries", value: "3")
            }
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
            .disabled(true)
            .opacity(0.4)
        }
    }

    private func advancedRow(icon: String, label: String, value: String) -> some View {
        HStack(spacing: CawnexSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 13))
                .foregroundStyle(CawnexColors.mutedForeground)
            VStack(alignment: .leading, spacing: 1) {
                Text(label)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
                Text(value)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
            }
        }
    }

    // MARK: - Helpers

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(CawnexTypography.label)
            .foregroundStyle(CawnexColors.mutedForeground)
            .tracking(1.2)
    }

    private func inputField(label: String, placeholder: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
            Text(label)
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            TextField(placeholder, text: text)
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
}

// MARK: - Previews

#Preview("Empty") {
    CreateCrowScreen(viewModel: CreateCrowViewModel())
}

#Preview("Filled") {
    let viewModel = CreateCrowViewModel()
    viewModel.name = "Planner"
    viewModel.role = "Planner"
    viewModel.goal = "Break down goals into executable tasks"
    viewModel.description = "Reads the project backlog and decomposes each goal into atomic, testable tasks with clear acceptance criteria."
    return CreateCrowScreen(viewModel: viewModel)
}
