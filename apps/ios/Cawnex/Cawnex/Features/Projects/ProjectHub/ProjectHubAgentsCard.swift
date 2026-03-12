import SwiftUI

struct ProjectHubAgentsCard: View {
    let murders: [MurderSummary]

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            cardHeader
            VStack(spacing: CawnexSpacing.sm) {
                ForEach(murders) { murder in
                    murderRow(murder)
                }
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    private var cardHeader: some View {
        HStack {
            HStack(spacing: 10) {
                Image("crow-icon")
                    .renderingMode(.template)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 20, height: 20)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text("Assigned Murders")
                    .font(CawnexTypography.subheading)
                    .foregroundStyle(CawnexColors.cardForeground)
            }
            Spacer()
            Text("Manage")
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.primary)
        }
    }

    private func murderRow(_ murder: MurderSummary) -> some View {
        HStack {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(dotColor(for: murder))
                    .frame(width: 8, height: 8)
                Text(murder.name)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
            }
            Spacer()
            Text("\(murder.crowCount) crows · \(murder.isActive ? "Active" : "Idle")")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    private func dotColor(for murder: MurderSummary) -> Color {
        murder.isActive ? CawnexColors.success : CawnexColors.info
    }
}
