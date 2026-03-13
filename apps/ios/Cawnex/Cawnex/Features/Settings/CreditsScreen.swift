import SwiftUI

struct CreditsScreen: View {
    @State var viewModel: CreditsViewModel
    var onBack: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                CawnexNavBar(
                    title: "Credits & Billing",
                    backColor: CawnexColors.primaryLight,
                    onBack: onBack
                )

                if case .loading = viewModel.state {
                    loadingView
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                }

                if let data = viewModel.data {
                    roiCard(roi: data.roi)
                    balanceCard(balance: data.balance)
                    projectBudgetsSection(budgets: data.projectBudgets)
                    costBreakdownSection(entries: data.costBreakdown, period: data.breakdownPeriod)
                    crowCostsCard(crows: data.crowCosts)
                }
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, CawnexSpacing.xl)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load() }
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading billing data…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - ROI Summary Card

    private func roiCard(roi: ROISummary) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "arrow.up.right.circle.fill")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(CawnexColors.accent)
                Text("ROI Summary")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Spacer()
                Text("\(roi.roiMultiplier)x ROI")
                    .font(CawnexTypography.monoBold)
                    .foregroundStyle(CawnexColors.accent)
            }

            Rectangle()
                .fill(CawnexColors.border)
                .frame(height: 1)

            HStack(alignment: .center, spacing: 0) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(formatCurrency(roi.humanEquivSaved))
                        .font(CawnexTypography.heading2)
                        .foregroundStyle(CawnexColors.success)
                    Text("human equiv. saved")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 2) {
                    Text(formatCurrency(roi.creditsSpent))
                        .font(CawnexTypography.heading2)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text("credits spent")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }

            HStack(spacing: CawnexSpacing.xl) {
                roiDetailPill(
                    icon: "clock.fill",
                    value: "\(roi.aiMinutes) min",
                    label: "AI time"
                )
                roiDetailPill(
                    icon: "person.fill",
                    value: "\(roi.humanHours) hrs",
                    label: "Human equiv"
                )
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .strokeBorder(CawnexColors.accent.opacity(0.35), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    private func roiDetailPill(icon: String, value: String, label: String) -> some View {
        HStack(spacing: CawnexSpacing.xs) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundStyle(CawnexColors.mutedForeground)
            VStack(alignment: .leading, spacing: 1) {
                Text(value)
                    .font(CawnexTypography.footnoteMedium)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text(label)
                    .font(CawnexTypography.tiny)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
        }
    }

    // MARK: - Credit Balance Card

    private func balanceCard(balance: CreditBalance) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "creditcard.fill")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(CawnexColors.primaryLight)
                Text("Credit Balance")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
            }

            Text(formatCurrencyPrecise(balance.remaining))
                .font(CawnexTypography.heading0)
                .foregroundStyle(CawnexColors.cardForeground)

            balanceProgressBar(ratio: balance.spentRatio)

            HStack {
                HStack(spacing: CawnexSpacing.xs) {
                    Circle()
                        .fill(CawnexColors.primary)
                        .frame(width: 8, height: 8)
                    Text("Spent \(formatCurrencyPrecise(balance.spent))")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }

                Spacer()

                HStack(spacing: CawnexSpacing.xs) {
                    Circle()
                        .fill(CawnexColors.success)
                        .frame(width: 8, height: 8)
                    Text("Remaining \(formatCurrencyPrecise(balance.remaining))")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .strokeBorder(CawnexColors.primaryLight.opacity(0.35), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    private func balanceProgressBar(ratio: Double) -> some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(CawnexColors.success.opacity(0.18))
                    .frame(maxWidth: .infinity)

                RoundedRectangle(cornerRadius: 4)
                    .fill(CawnexColors.primary)
                    .frame(width: max(geometry.size.width * ratio, 6))
            }
        }
        .frame(height: 8)
    }

    // MARK: - Project Budgets Section

    private func projectBudgetsSection(budgets: [ProjectBudget]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack {
                Text("Project Budgets")
                    .font(CawnexTypography.sectionTitle)
                    .foregroundStyle(CawnexColors.cardForeground)
                Spacer()
                Button("Set") {}
                    .buttonStyle(.plain)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.primaryLight)
                    .disabled(true)
                    .opacity(0.4)
            }

            VStack(spacing: CawnexSpacing.sm) {
                ForEach(budgets) { budget in
                    projectBudgetCard(budget: budget)
                }
            }
        }
    }

    private func projectBudgetCard(budget: ProjectBudget) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack {
                Text(budget.projectName)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Spacer()
                Text("\(formatCurrencyWhole(budget.spent)) of \(formatCurrencyWhole(budget.total))")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(CawnexColors.muted)
                        .frame(maxWidth: .infinity)

                    RoundedRectangle(cornerRadius: 3)
                        .fill(CawnexColors.primaryLight)
                        .frame(width: max(geometry.size.width * budget.spentRatio, 6))
                }
            }
            .frame(height: 6)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Cost Breakdown Section

    private func costBreakdownSection(entries: [CostBreakdownEntry], period: String) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack {
                Text("Cost Breakdown")
                    .font(CawnexTypography.sectionTitle)
                    .foregroundStyle(CawnexColors.cardForeground)
                Spacer()
                Text(period)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .padding(.horizontal, CawnexSpacing.sm)
                    .padding(.vertical, CawnexSpacing.xs)
                    .background(CawnexColors.muted)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
            }

            VStack(spacing: 0) {
                ForEach(Array(entries.enumerated()), id: \.element.id) { index, entry in
                    costBreakdownRow(entry: entry)
                    if index < entries.count - 1 {
                        Rectangle()
                            .fill(CawnexColors.border)
                            .frame(height: 1)
                    }
                }
            }
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    private func costBreakdownRow(entry: CostBreakdownEntry) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(entry.projectName)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text("\(entry.taskCount) tasks")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
            Text(formatCurrencyWhole(entry.amount))
                .font(CawnexTypography.monoBold)
                .foregroundStyle(CawnexColors.cardForeground)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .frame(height: 56)
    }

    // MARK: - Crow Costs Card

    private func crowCostsCard(crows: [CrowCost]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "bird.fill")
                    .font(.system(size: 13))
                    .foregroundStyle(CawnexColors.primaryLight)
                Text("Crow Costs")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
            }
            .padding(.bottom, CawnexSpacing.xs)

            VStack(spacing: CawnexSpacing.xs) {
                ForEach(crows) { crow in
                    crowCostRow(crow: crow)
                }
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    private func crowCostRow(crow: CrowCost) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(crow.crowName)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text(crow.role)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
            Text(formatCurrencyPrecise(crow.amount))
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.cardForeground)
        }
        .padding(.vertical, CawnexSpacing.sm)
        .padding(.horizontal, CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    // MARK: - Formatters

    private func formatCurrency(_ value: Decimal) -> String {
        let number = NSDecimalNumber(decimal: value).doubleValue
        if number >= 1000 {
            return "$\(String(format: "%.0f", number / 1000))k"
        }
        return "$\(String(format: "%.0f", number))"
    }

    private func formatCurrencyWhole(_ value: Decimal) -> String {
        let number = NSDecimalNumber(decimal: value).doubleValue
        return "$\(String(format: "%.0f", number))"
    }

    private func formatCurrencyPrecise(_ value: Decimal) -> String {
        let number = NSDecimalNumber(decimal: value).doubleValue
        return "$\(String(format: "%.2f", number))"
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return CreditsScreen(
        viewModel: CreditsViewModel(
            creditsService: InMemoryCreditsService(store: store)
        )
    )
}
