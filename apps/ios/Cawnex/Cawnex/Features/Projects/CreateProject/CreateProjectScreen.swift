import SwiftUI

struct CreateProjectScreen: View {
    @State var viewModel: CreateProjectViewModel
    var onCancel: () -> Void = {}
    var onCreate: (Project) -> Void = { _ in }

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
                        oneLinerField
                        murdersSection
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

            Text("New Project")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Text("Cancel")
                .font(CawnexTypography.body)
                .foregroundStyle(.clear)
        }
    }

    // MARK: - Hero Section

    private var heroSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("What are we building?")
                .font(CawnexTypography.heading1)
                .foregroundStyle(CawnexColors.cardForeground)

            Text("Give your project a name. Our AI will help\nyou shape everything else.")
                .font(CawnexTypography.tagline)
                .foregroundStyle(CawnexColors.mutedForeground)
                .lineSpacing(6)
        }
    }

    // MARK: - Name Field

    private var nameField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("PROJECT NAME")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            TextField("e.g. Cawnex, Calhou, My SaaS…", text: $viewModel.name)
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

    // MARK: - One-Liner Field

    private var oneLinerField: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("ONE-LINER")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            TextField("What does it do in one sentence?", text: $viewModel.oneLiner)
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

            Text("Optional — AI will refine this during Vision setup")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Murders Section

    private var murdersSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
                Text("MURDERS")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .tracking(1.2)

                Text("Which AI teams should work on this project?")
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            murderChips

            Text("Dev Murder is selected by default. Tap to toggle.")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private var murderChips: some View {
        FlowLayout(spacing: CawnexSpacing.sm) {
            ForEach(MurderType.allCases) { murder in
                murderChip(murder)
            }
        }
    }

    private func murderChip(_ murder: MurderType) -> some View {
        let isSelected = viewModel.selectedMurders.contains(murder)
        return Button {
            viewModel.toggleMurder(murder)
        } label: {
            HStack(spacing: CawnexSpacing.xs) {
                Image(systemName: murder.sfIcon)
                    .font(.system(size: 13, weight: .medium))
                Text(murder.displayName)
                    .font(isSelected ? CawnexTypography.captionBold : CawnexTypography.captionMedium)
            }
            .foregroundStyle(isSelected ? .white : CawnexColors.mutedForeground)
            .padding(.horizontal, 14)
            .frame(height: 36)
            .background(isSelected ? CawnexColors.primaryLight : CawnexColors.muted)
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }

    // MARK: - CTA Bar

    private var ctaBar: some View {
        VStack(spacing: CawnexSpacing.md) {
            Button {
                Task {
                    if let project = await viewModel.create() {
                        onCreate(project)
                    }
                }
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.85)
                    } else {
                        Image(systemName: "paperplane.fill")
                            .font(.system(size: 15, weight: .bold))
                    }
                    Text("Create Project")
                        .font(CawnexTypography.sectionTitle)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(viewModel.canCreate ? CawnexColors.primaryLight : CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)
            .disabled(!viewModel.canCreate || viewModel.isSubmitting)

            Text("You'll set up Vision, Architecture & more next")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
                .multilineTextAlignment(.center)
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
    return CreateProjectScreen(
        viewModel: CreateProjectViewModel(
            projectService: InMemoryProjectService(store: store)
        )
    )
}
