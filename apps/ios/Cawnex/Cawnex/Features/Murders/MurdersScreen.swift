import SwiftUI

struct MurdersScreen: View {
    @State var viewModel: MurdersViewModel
    var onNewMurder: () -> Void = {}
    var onMurderTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                // Header
                HStack {
                    Text("Murders")
                        .font(CawnexTypography.heading1)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Spacer()
                    Button(action: onNewMurder) {
                        HStack(spacing: 6) {
                            Image(systemName: "plus")
                                .font(.system(size: 12, weight: .bold))
                            Text("New Murder")
                                .font(CawnexTypography.captionBold)
                        }
                        .foregroundStyle(.white)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(CawnexColors.primary)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    }
                    .buttonStyle(.plain)
                }

                if case .loading = viewModel.state {
                    loadingView
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                }

                if let data = viewModel.data {
                    // Your Murders
                    VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                        Text("Your Murders")
                            .font(CawnexTypography.footnoteMedium)
                            .foregroundStyle(CawnexColors.mutedForeground)
                            .tracking(1)

                        ForEach(data.murders) { murder in
                            murderCard(murder)
                        }
                    }

                    // Divider
                    Rectangle()
                        .fill(CawnexColors.border)
                        .frame(height: 1)

                    // Marketplace
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
            Text("Loading murders…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - Murder Card

    private func murderCard(_ murder: Murder) -> some View {
        Button { onMurderTap(murder.id) } label: {
            VStack(alignment: .leading, spacing: 14) {
                // Top row: avatar + info + chevron
                HStack(spacing: CawnexSpacing.md) {
                    murderAvatar(murder)

                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: CawnexSpacing.sm) {
                            Text(murder.name)
                                .font(CawnexTypography.bodyBold)
                                .foregroundStyle(CawnexColors.cardForeground)
                            Text(murder.status.rawValue)
                                .font(CawnexTypography.label)
                                .foregroundStyle(murder.status.color)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 2)
                                .background(murder.status.color.opacity(0.13))
                                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.pill))
                        }
                        Text(murder.description)
                            .font(CawnexTypography.footnote)
                            .foregroundStyle(CawnexColors.mutedForeground)
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.system(size: 14))
                        .foregroundStyle(CawnexColors.mutedForeground)
                }

                // Behavior status panel (active murders only)
                if !murder.behaviorLines.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(murder.behaviorLines) { line in
                            HStack(spacing: CawnexSpacing.sm) {
                                Circle()
                                    .fill(line.color)
                                    .frame(width: 8, height: 8)
                                Text(line.text)
                                    .font(CawnexTypography.footnoteMedium)
                                    .foregroundStyle(line.color)
                            }
                        }
                    }
                    .padding(.horizontal, CawnexSpacing.md)
                    .padding(.vertical, CawnexSpacing.md)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(CawnexColors.deepNavy)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }

                // Crow chips
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: CawnexSpacing.sm) {
                        ForEach(murder.crows) { crow in
                            crowChip(crow)
                        }
                    }
                }

                // Stats row (active murders only)
                if murder.tasksDone > 0 {
                    HStack {
                        statColumn(value: "\(murder.tasksDone)", label: "tasks done")
                        Spacer()
                        statColumn(
                            value: "\(murder.successRate)%",
                            label: "success",
                            valueColor: CawnexColors.success
                        )
                        Spacer()
                        statColumn(value: "$\(murder.totalCost as NSDecimalNumber)", label: "total cost")
                    }
                }
            }
            .padding(CawnexSpacing.lg)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(
                        murder.status == .active ? CawnexColors.success.opacity(0.27) : .clear,
                        lineWidth: 1
                    )
            )
        }
        .buttonStyle(.plain)
    }

    private func murderAvatar(_ murder: Murder) -> some View {
        Image(systemName: murder.icon)
            .font(.system(size: 20))
            .foregroundStyle(.white)
            .frame(width: 44, height: 44)
            .background(
                murder.status == .active
                    ? LinearGradient(
                        colors: [CawnexColors.primary, CawnexColors.primaryLight],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    : LinearGradient(
                        colors: [CawnexColors.muted, CawnexColors.muted],
                        startPoint: .top,
                        endPoint: .bottom
                    )
            )
            .clipShape(Circle())
    }

    private func crowChip(_ crow: CrowSummary) -> some View {
        HStack(spacing: 6) {
            if crow.isActive {
                Image(systemName: "bird.fill")
                    .font(.system(size: 12))
                    .foregroundStyle(crow.activityColor)
            } else {
                Circle()
                    .fill(crow.activityColor)
                    .frame(width: 8, height: 8)
            }
            Text(crow.name)
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(crow.isActive ? CawnexColors.cardForeground : CawnexColors.mutedForeground)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.pill))
    }

    private func statColumn(value: String, label: String, valueColor: Color = CawnexColors.cardForeground) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(CawnexTypography.monoBold)
                .foregroundStyle(valueColor)
            Text(label)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Marketplace

    private func marketplaceSection(items: [MarketplaceMurder]) -> some View {
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

            Text("Community murder templates ready to install")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)

            ForEach(items) { item in
                marketplaceCard(item)
            }
        }
    }

    private func marketplaceCard(_ item: MarketplaceMurder) -> some View {
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
    return MurdersScreen(
        viewModel: MurdersViewModel(
            murdersService: InMemoryMurdersService(store: store)
        )
    )
    .environment(store)
}
