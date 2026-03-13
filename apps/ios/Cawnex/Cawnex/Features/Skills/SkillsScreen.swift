import SwiftUI

struct SkillsScreen: View {
    @State var viewModel: SkillsViewModel
    var onNewSkill: () -> Void = {}
    var onSkillTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                // Header
                HStack {
                    Text("Skills")
                        .font(CawnexTypography.heading0)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Spacer()
                    Button(action: onNewSkill) {
                        HStack(spacing: 6) {
                            Image(systemName: "plus")
                                .font(.system(size: 12, weight: .bold))
                            Text("New Skill")
                                .font(CawnexTypography.captionBold)
                        }
                        .foregroundStyle(.white)
                        .padding(.horizontal, CawnexSpacing.lg)
                        .padding(.vertical, CawnexSpacing.sm)
                        .background(CawnexColors.primary)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    }
                    .buttonStyle(.plain)
                }

                Text("Skills define what crows can do. Attach skills to murders to shape their capabilities.")
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)

                if case .loading = viewModel.state {
                    loadingView
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                }

                if let data = viewModel.data {
                    filterChips
                    skillsSection
                    Rectangle()
                        .fill(CawnexColors.border)
                        .frame(height: 1)
                    marketplaceSection(items: data.marketplace)
                }
            }
            .padding(.top, CawnexSpacing.lg)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, 100)
        }
        .background(CawnexColors.background)
        .task { await viewModel.load() }
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading skills…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - Filter Chips

    private var filterChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: CawnexSpacing.sm) {
                filterChip(label: "All", isSelected: viewModel.selectedCategory == nil) {
                    viewModel.selectCategory(nil)
                }
                ForEach(SkillCategory.allCases, id: \.self) { category in
                    filterChip(label: category.rawValue, isSelected: viewModel.selectedCategory == category) {
                        viewModel.selectCategory(category)
                    }
                }
            }
        }
    }

    private func filterChip(label: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(CawnexTypography.captionBold)
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 6)
                .background(isSelected ? CawnexColors.primary : CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.lg))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Skills Section

    private var skillsSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            Text("Your Skills")
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1)

            ForEach(viewModel.filteredSkills) { skill in
                skillCard(skill)
            }
        }
    }

    private func skillCard(_ skill: Skill) -> some View {
        Button { onSkillTap(skill.id) } label: {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                // Top: icon + name + category badge
                HStack {
                    HStack(spacing: CawnexSpacing.sm) {
                        Image(systemName: skill.icon)
                            .font(.system(size: 18))
                            .foregroundStyle(skill.category.color)
                        Text(skill.name)
                            .font(CawnexTypography.bodyBold)
                            .foregroundStyle(CawnexColors.cardForeground)
                    }
                    Spacer()
                    Text(skill.category.rawValue)
                        .font(CawnexTypography.tinyMedium)
                        .foregroundStyle(skill.category.color)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 3)
                        .background(skill.category.color.opacity(0.2))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                }

                // Description
                Text(skill.description)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .lineLimit(2)

                // Meta
                HStack {
                    Text("Used by: \(skill.usedBy)")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                    Spacer()
                    Text("\(skill.useCount) uses")
                        .font(CawnexTypography.mono)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Marketplace

    private func marketplaceSection(items: [MarketplaceSkill]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: "storefront.fill")
                        .font(.system(size: 16))
                        .foregroundStyle(CawnexColors.primaryLight)
                    Text("Marketplace")
                        .font(CawnexTypography.heading3)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                Spacer()
                Button {} label: {
                    Text("See all")
                        .font(CawnexTypography.captionMedium)
                        .foregroundStyle(CawnexColors.primaryLight)
                }
                .buttonStyle(.plain)
                .disabled(true)
                .opacity(0.4)
            }

            Text("Community skills ready to add to your murders")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)

            ForEach(items) { item in
                marketplaceCard(item)
            }
        }
    }

    private func marketplaceCard(_ item: MarketplaceSkill) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: item.icon)
                        .font(.system(size: 18))
                        .foregroundStyle(item.iconColor)
                    Text(item.name)
                        .font(CawnexTypography.bodyBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                Spacer()
                Button {} label: {
                    Text("Install")
                        .font(CawnexTypography.label)
                        .foregroundStyle(.white)
                        .padding(.horizontal, CawnexSpacing.md)
                        .padding(.vertical, 4)
                        .background(CawnexColors.muted)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.lg))
                }
                .buttonStyle(.plain)
                .disabled(true)
                .opacity(0.4)
            }

            Text(item.description)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: CawnexSpacing.sm) {
                Text("★ \(String(format: "%.1f", item.rating))")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.warning)
                Text("· \(item.installs) installs")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
                Text("· by \(item.author)")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return SkillsScreen(
        viewModel: SkillsViewModel(
            skillsService: InMemorySkillsService(store: store)
        )
    )
    .environment(store)
}
