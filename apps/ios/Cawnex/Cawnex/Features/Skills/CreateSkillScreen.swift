import SwiftUI

struct CreateSkillScreen: View {
    @State var viewModel: CreateSkillViewModel
    var onCancel: () -> Void = {}
    var onSave: (Skill) -> Void = { _ in }

    var body: some View {
        ZStack(alignment: .bottom) {
            CawnexColors.background.ignoresSafeArea()

            VStack(spacing: 0) {
                navRow
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.top, CawnexSpacing.lg)
                    .padding(.bottom, CawnexSpacing.md)

                ScrollView {
                    VStack(alignment: .leading, spacing: CawnexSpacing.xxxl) {
                        identitySection
                        parametersSection
                        behaviorSection
                        securitySection
                        executionSection
                        testSection
                    }
                    .padding(.top, CawnexSpacing.xl)
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
                .buttonStyle(.plain)

            Spacer()

            Text("New Skill")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Button("Save") {
                Task {
                    if let skill = await viewModel.submit() {
                        onSave(skill)
                    }
                }
            }
            .font(CawnexTypography.bodyBold)
            .foregroundStyle(viewModel.canSubmit ? CawnexColors.primaryLight : CawnexColors.mutedForeground)
            .buttonStyle(.plain)
            .disabled(!viewModel.canSubmit || viewModel.isSubmitting)
        }
    }

    // MARK: - Section Header

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(CawnexTypography.label)
            .foregroundStyle(CawnexColors.mutedForeground)
            .tracking(1.2)
    }

    // MARK: - Text Field Style

    private func styledTextField(_ placeholder: String, text: Binding<String>) -> some View {
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

    // MARK: - Identity Section

    private var identitySection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            sectionHeader("IDENTITY")

            nameField
            displayNameField
            iconCategoryRow
            descriptionField
            tagsField
        }
    }

    private var nameField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("Name")
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            styledTextField("e.g. code-review", text: $viewModel.name)
        }
    }

    private var displayNameField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("Display Name")
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            styledTextField("e.g. Code Review", text: $viewModel.displayName)
        }
    }

    private var iconCategoryRow: some View {
        HStack(spacing: CawnexSpacing.md) {
            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("Icon")
                    .font(CawnexTypography.captionMedium)
                    .foregroundStyle(CawnexColors.mutedForeground)

                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: viewModel.icon)
                        .font(.system(size: 18))
                        .foregroundStyle(viewModel.category.color)
                        .frame(width: 24)

                    TextField("bolt.fill", text: $viewModel.icon)
                        .font(CawnexTypography.mono)
                        .foregroundStyle(CawnexColors.cardForeground)
                        .tint(CawnexColors.primaryLight)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                }
                .frame(height: 48)
                .padding(.horizontal, CawnexSpacing.md)
                .background(CawnexColors.card)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CawnexRadius.md)
                        .stroke(CawnexColors.border, lineWidth: 1)
                )
            }
            .frame(maxWidth: .infinity)

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("Category")
                    .font(CawnexTypography.captionMedium)
                    .foregroundStyle(CawnexColors.mutedForeground)

                Menu {
                    ForEach(SkillCategory.allCases, id: \.self) { cat in
                        Button(cat.rawValue) {
                            viewModel.category = cat
                        }
                    }
                } label: {
                    HStack {
                        Text(viewModel.category.rawValue)
                            .font(CawnexTypography.body)
                            .foregroundStyle(viewModel.category.color)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(CawnexColors.mutedForeground)
                    }
                    .frame(height: 48)
                    .padding(.horizontal, CawnexSpacing.md)
                    .background(CawnexColors.card)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(CawnexColors.border, lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)
            }
            .frame(maxWidth: .infinity)
        }
    }

    private var descriptionField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("Description")
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            TextField("What does this skill do?", text: $viewModel.description, axis: .vertical)
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

    private var tagsField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("Tags")
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            styledTextField("review, lint, analysis…", text: $viewModel.tags)

            Text("Comma-separated — used to discover and filter skills")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Input Parameters Section (static preview)

    private var parametersSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            sectionHeader("INPUT PARAMETERS")

            VStack(spacing: CawnexSpacing.sm) {
                parameterCard(name: "repo_url", type: "string", required: true)
                parameterCard(name: "branch", type: "string", required: false)
            }
            .disabled(true)
            .opacity(0.4)

            HStack {
                Button {} label: {
                    HStack(spacing: CawnexSpacing.xs) {
                        Image(systemName: "plus")
                            .font(.system(size: 12, weight: .bold))
                        Text("Add Parameter")
                            .font(CawnexTypography.captionBold)
                    }
                    .foregroundStyle(CawnexColors.primaryLight)
                    .padding(.horizontal, CawnexSpacing.md)
                    .padding(.vertical, CawnexSpacing.sm)
                    .background(CawnexColors.primaryLight.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                }
                .buttonStyle(.plain)
                .disabled(true)
                .opacity(0.4)

                Spacer()
            }

            strictModeRow
                .disabled(true)
                .opacity(0.4)
        }
    }

    private func parameterCard(name: String, type: String, required: Bool) -> some View {
        HStack(spacing: CawnexSpacing.md) {
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(CawnexTypography.mono)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text(type)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            Spacer()

            Text("Required")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)

            Toggle("", isOn: .constant(required))
                .tint(CawnexColors.primaryLight)
                .labelsHidden()
                .scaleEffect(0.85)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    private var strictModeRow: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Strict Mode")
                    .font(CawnexTypography.bodyBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text("Reject calls with undeclared parameters")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
            Toggle("", isOn: .constant(false))
                .tint(CawnexColors.primaryLight)
                .labelsHidden()
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    // MARK: - Behavior Section (static preview)

    private var behaviorSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            sectionHeader("BEHAVIOR")

            VStack(spacing: 0) {
                settingsRow(label: "Max Retries", value: "3")
                Divider().background(CawnexColors.border)
                settingsRow(label: "Timeout", value: "30s")
                Divider().background(CawnexColors.border)
                settingsRow(label: "Output Format", value: "JSON")
                Divider().background(CawnexColors.border)
                settingsToggleRow(label: "Cache Results", value: true)
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

    // MARK: - Security & Permissions Section (static preview)

    private var securitySection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            sectionHeader("SECURITY & PERMISSIONS")

            VStack(spacing: 0) {
                settingsToggleRow(label: "Requires Auth", value: true)
                Divider().background(CawnexColors.border)
                settingsRow(label: "Access Level", value: "Project")
                Divider().background(CawnexColors.border)
                settingsToggleRow(label: "Audit Logging", value: false)
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

    // MARK: - Execution Section (static preview)

    private var executionSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            sectionHeader("EXECUTION")

            VStack(spacing: 0) {
                settingsRow(label: "Runtime", value: "Node 20")
                Divider().background(CawnexColors.border)
                settingsRow(label: "Memory Limit", value: "512 MB")
                Divider().background(CawnexColors.border)
                settingsRow(label: "Concurrency", value: "Sequential")
                Divider().background(CawnexColors.border)
                settingsToggleRow(label: "Dry Run Mode", value: false)
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

    // MARK: - Test Section (static preview)

    private var testSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            sectionHeader("TEST")

            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                Text("Test Input")
                    .font(CawnexTypography.captionMedium)
                    .foregroundStyle(CawnexColors.mutedForeground)

                Text("{ \"repo_url\": \"https://github.com/org/repo\", \"branch\": \"main\" }")
                    .font(CawnexTypography.mono)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .padding(CawnexSpacing.md)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(CawnexColors.card)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(CawnexColors.border, lineWidth: 1)
                    )

                Button {} label: {
                    HStack(spacing: CawnexSpacing.sm) {
                        Image(systemName: "play.fill")
                            .font(.system(size: 12, weight: .bold))
                        Text("Run Test")
                            .font(CawnexTypography.captionBold)
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 44)
                    .background(CawnexColors.muted)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                }
                .buttonStyle(.plain)
            }
            .disabled(true)
            .opacity(0.4)
        }
    }

    // MARK: - Shared Row Components

    private func settingsRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)
            Spacer()
            Text(value)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)
            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.md)
    }

    private func settingsToggleRow(label: String, value: Bool) -> some View {
        HStack {
            Text(label)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)
            Spacer()
            Toggle("", isOn: .constant(value))
                .tint(CawnexColors.primaryLight)
                .labelsHidden()
                .scaleEffect(0.85)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
    }

    // MARK: - CTA Bar

    private var ctaBar: some View {
        VStack(spacing: CawnexSpacing.md) {
            Button {
                Task {
                    if let skill = await viewModel.submit() {
                        onSave(skill)
                    }
                }
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.85)
                    } else {
                        Image(systemName: "plus")
                            .font(.system(size: 15, weight: .bold))
                    }
                    Text("Create Skill")
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
                Text("Parameters, Behavior and Execution can be refined later")
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

// MARK: - Previews

#Preview("Empty") {
    CreateSkillScreen(viewModel: CreateSkillViewModel())
}

#Preview("Filled") {
    let viewModel = CreateSkillViewModel()
    viewModel.name = "code-review"
    viewModel.displayName = "Code Review"
    viewModel.icon = "magnifyingglass.circle.fill"
    viewModel.category = .dev
    viewModel.description = "Performs automated code review on pull requests, checking for style, security, and performance issues."
    viewModel.tags = "review, lint, pr, analysis"
    return CreateSkillScreen(viewModel: viewModel)
}
