import SwiftUI

struct DocPreviewBanner: View {
    let title: String
    let accentColor: Color
    let sectionsComplete: Int
    let sectionsTotal: Int

    private var progress: Double {
        guard sectionsTotal > 0 else { return 0 }
        return Double(sectionsComplete) / Double(sectionsTotal)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack {
                Image(systemName: "doc.text")
                    .font(.system(size: 14))
                    .foregroundStyle(accentColor)
                Text(title)
                    .font(CawnexTypography.subheading)
                    .foregroundStyle(CawnexColors.cardForeground)
                Spacer()
                Image(systemName: "chevron.down")
                    .font(.system(size: 12))
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            HStack(spacing: CawnexSpacing.sm) {
                Text("\(sectionsComplete) of \(sectionsTotal) sections")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)

                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(CawnexColors.muted)
                            .frame(height: 4)
                        RoundedRectangle(cornerRadius: 2)
                            .fill(accentColor)
                            .frame(width: geo.size.width * progress, height: 4)
                    }
                }
                .frame(height: 4)
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(accentColor.opacity(0.27), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        DocPreviewBanner(
            title: "Vision Document",
            accentColor: CawnexColors.primary,
            sectionsComplete: 2,
            sectionsTotal: 6
        )
        .padding(CawnexSpacing.xl)
    }
}
