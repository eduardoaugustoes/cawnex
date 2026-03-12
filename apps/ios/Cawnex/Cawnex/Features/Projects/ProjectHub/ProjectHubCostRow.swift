import SwiftUI

struct ProjectHubCostRow: View {
    let project: Project
    let roi: Int

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "wallet.bifold")
                        .font(.system(size: 14))
                        .foregroundStyle(CawnexColors.primary)
                    Text("This month")
                        .font(CawnexTypography.footnoteMedium)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                Text("\(roi)x ROI")
                    .font(CawnexTypography.monoBold)
                    .foregroundStyle(CawnexColors.accent)
            }

            BudgetBar(spent: project.creditsSpent, saved: project.humanEquivSaved)
        }
        .padding(.horizontal, CawnexSpacing.lg)
        .padding(.vertical, 14)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }
}
