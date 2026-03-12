import SwiftUI

struct BudgetBar: View {
    let spent: Decimal
    let saved: Decimal

    private var ratio: CGFloat {
        let total = NSDecimalNumber(decimal: spent + saved).doubleValue
        guard total > 0 else { return 0 }
        return CGFloat(NSDecimalNumber(decimal: spent).doubleValue / total)
    }

    var body: some View {
        HStack(spacing: CawnexSpacing.sm) {
            Text("Spent \(formatCurrency(spent))")
                .font(.custom("JetBrains Mono", size: 11).weight(.semibold))
                .foregroundStyle(CawnexColors.mutedForeground)
                .fixedSize()

            GeometryReader { geometry in
                HStack(spacing: 0) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(CawnexColors.primary)
                        .frame(width: max(geometry.size.width * ratio, 5))
                    RoundedRectangle(cornerRadius: 3)
                        .fill(CawnexColors.success)
                }
            }
            .frame(height: 6)
            .background(CawnexColors.success.opacity(0.13))
            .clipShape(RoundedRectangle(cornerRadius: 3))

            Text("Saved \(formatCurrency(saved))")
                .font(.custom("JetBrains Mono", size: 11).weight(.semibold))
                .foregroundStyle(CawnexColors.success)
                .fixedSize()
        }
    }

    private func formatCurrency(_ value: Decimal) -> String {
        let number = NSDecimalNumber(decimal: value).doubleValue
        if number >= 1000 {
            return "~$\(String(format: "%.0f", number / 1000))k"
        }
        return "$\(String(format: "%.0f", number))"
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        BudgetBar(spent: 182, saved: 14000)
            .padding()
    }
}
