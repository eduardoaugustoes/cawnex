import SwiftUI

struct CreateMurderScreen: View {
    @State var viewModel: CreateMurderViewModel
    var onCancel: () -> Void = {}
    var onSave: (Murder) -> Void = { _ in }

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
                        descriptionSection
                        crowsSection
                        murderPromptSection
                        qualityGatesSection
                        budgetSection
                        crowFlowSection
                        escalationSection
                    }
                    .padding(.top, CawnexSpacing.xxl)
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.bottom, 60)
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

            Text("New Murder")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Button {
                Task {
                    if let murder = await viewModel.submit() {
                        onSave(murder)
                    }
                }
            } label: {
                Group {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.8)
                    } else {
                        Text("Save")
                            .font(CawnexTypography.bodyBold)
                    }
                }
                .foregroundStyle(.white)
                .padding(.horizontal, CawnexSpacing.md)
                .padding(.vertical, 6)
                .background(viewModel.canSubmit ? CawnexColors.primary : CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)
            .disabled(!viewModel.canSubmit || viewModel.isSubmitting)
        }
    }

    // MARK: - Identity Section

    private var identitySection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            sectionHeader("IDENTITY")

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("NAME")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .tracking(1.2)

                TextField("e.g. Dev Murder", text: $viewModel.name)
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

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("MURDER TYPE")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .tracking(1.2)

                murderTypeSelector
            }
        }
    }

    private var murderTypeSelector: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ForEach(MurderType.allCases) { type in
                Button {
                    viewModel.murderType = type
                } label: {
                    VStack(spacing: CawnexSpacing.xs) {
                        Image(systemName: type.sfIcon)
                            .font(.system(size: 16, weight: .medium))
                            .foregroundStyle(
                                viewModel.murderType == type
                                    ? CawnexColors.primaryLight
                                    : CawnexColors.mutedForeground
                            )

                        Text(type.displayName)
                            .font(CawnexTypography.tinyMedium)
                            .foregroundStyle(
                                viewModel.murderType == type
                                    ? CawnexColors.primaryLight
                                    : CawnexColors.mutedForeground
                            )
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, CawnexSpacing.md)
                    .background(
                        viewModel.murderType == type
                            ? CawnexColors.primary.opacity(0.18)
                            : CawnexColors.card
                    )
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(
                                viewModel.murderType == type
                                    ? CawnexColors.primaryLight.opacity(0.5)
                                    : CawnexColors.border,
                                lineWidth: 1
                            )
                    )
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Description Section

    private var descriptionSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("DESCRIPTION")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            TextField(
                "What does this murder orchestrate?",
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

    // MARK: - Crows Section

    private var crowsSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
                Text("CROWS")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .tracking(1.2)

                Text("Select which crows belong to this murder")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            VStack(spacing: CawnexSpacing.sm) {
                ForEach(["Planner", "Implementer", "Reviewer"], id: \.self) { crowName in
                    staticCrowCard(crowName)
                }
            }
            .disabled(true)
            .opacity(0.4)
        }
    }

    private func staticCrowCard(_ name: String) -> some View {
        HStack(spacing: CawnexSpacing.md) {
            Image(systemName: "bird.fill")
                .font(.system(size: 14))
                .foregroundStyle(CawnexColors.primaryLight)
                .frame(width: 32, height: 32)
                .background(CawnexColors.primary.opacity(0.15))
                .clipShape(Circle())

            Text(name)
                .font(CawnexTypography.bodyBold)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 18))
                .foregroundStyle(CawnexColors.primaryLight)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.primaryLight.opacity(0.4), lineWidth: 1)
        )
    }

    // MARK: - Murder Prompt Section

    private var murderPromptSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("MURDER PROMPT")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("You are a specialized murder coordinating high-quality software development tasks. Each crow must follow TDD practices and produce clean, documented code.")
                    .font(CawnexTypography.body)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(CawnexSpacing.md)
                    .background(CawnexColors.card)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(CawnexColors.border, lineWidth: 1)
                    )

                Text("Injected as context into every crow's system prompt")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .disabled(true)
            .opacity(0.4)
        }
    }

    // MARK: - Quality Gates Section

    private var qualityGatesSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionHeader("QUALITY GATES")

            VStack(spacing: 0) {
                ForEach(qualityGateRows, id: \.0) { label, isOn in
                    qualityGateRow(label: label, isOn: isOn)
                    if label != qualityGateRows.last?.0 {
                        Divider()
                            .background(CawnexColors.border)
                            .padding(.horizontal, CawnexSpacing.md)
                    }
                }
            }
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

    private let qualityGateRows: [(String, Bool)] = [
        ("Require test coverage > 80%", true),
        ("Block merge on lint errors", true),
        ("Require peer review (Reviewer crow)", true),
        ("Auto-reject tasks > 8h estimate", false),
    ]

    private func qualityGateRow(label: String, isOn: Bool) -> some View {
        HStack {
            Text(label)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)
            Spacer()
            Toggle("", isOn: .constant(isOn))
                .tint(CawnexColors.primaryLight)
                .labelsHidden()
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.md)
    }

    // MARK: - Budget Section

    private var budgetSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionHeader("BUDGET LIMITS")

            VStack(spacing: 0) {
                budgetRow(label: "Monthly credit cap", value: "500 credits")
                Divider()
                    .background(CawnexColors.border)
                    .padding(.horizontal, CawnexSpacing.md)
                budgetRow(label: "Per-task credit limit", value: "50 credits")
                Divider()
                    .background(CawnexColors.border)
                    .padding(.horizontal, CawnexSpacing.md)
                budgetRow(label: "Alert threshold", value: "80%")
            }
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

    private func budgetRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)
            Spacer()
            Text(value)
                .font(CawnexTypography.bodyBold)
                .foregroundStyle(CawnexColors.primaryLight)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.md)
    }

    // MARK: - Crow Flow Section

    private var crowFlowSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionHeader("CROW FLOW")

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: CawnexSpacing.xs) {
                    ForEach(Array(["Planner", "Implementer", "Reviewer"].enumerated()), id: \.offset) { index, step in
                        flowStep(step)
                        if index < 2 {
                            Image(systemName: "arrow.right")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(CawnexColors.mutedForeground)
                        }
                    }
                }
                .padding(.horizontal, CawnexSpacing.xs)
            }
            .disabled(true)
            .opacity(0.4)
        }
    }

    private func flowStep(_ name: String) -> some View {
        VStack(spacing: CawnexSpacing.xs) {
            Image(systemName: "bird.fill")
                .font(.system(size: 14))
                .foregroundStyle(CawnexColors.primaryLight)
                .frame(width: 36, height: 36)
                .background(CawnexColors.primary.opacity(0.15))
                .clipShape(Circle())

            Text(name)
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(CawnexColors.cardForeground)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    // MARK: - Escalation Section

    private var escalationSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            sectionHeader("ESCALATION RULES")

            VStack(spacing: 0) {
                escalationRow(icon: "exclamationmark.triangle.fill", color: CawnexColors.warning, label: "Escalate after 3 failed retries")
                Divider()
                    .background(CawnexColors.destructive.opacity(0.3))
                    .padding(.horizontal, CawnexSpacing.md)
                escalationRow(icon: "bell.fill", color: CawnexColors.destructive, label: "Notify on budget threshold breach")
                Divider()
                    .background(CawnexColors.destructive.opacity(0.3))
                    .padding(.horizontal, CawnexSpacing.md)
                escalationRow(icon: "pause.circle.fill", color: CawnexColors.destructive, label: "Pause murder on critical error")
            }
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.destructive.opacity(0.35), lineWidth: 1)
            )
            .disabled(true)
            .opacity(0.4)
        }
    }

    private func escalationRow(icon: String, color: Color, label: String) -> some View {
        HStack(spacing: CawnexSpacing.md) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundStyle(color)
                .frame(width: 24)

            Text(label)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Toggle("", isOn: .constant(true))
                .tint(CawnexColors.destructive)
                .labelsHidden()
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.md)
    }

    // MARK: - Helpers

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(CawnexTypography.label)
            .foregroundStyle(CawnexColors.mutedForeground)
            .tracking(1.2)
    }
}

#Preview("Create Murder") {
    let store = AppStore()
    store.seedData()
    return CreateMurderScreen(
        viewModel: CreateMurderViewModel()
    )
    .environment(store)
}
