import SwiftUI

struct PipelineBar: View {
    let done: Int
    let active: Int
    let refined: Int
    let draft: Int

    private var total: Int { done + active + refined + draft }

    var body: some View {
        GeometryReader { geometry in
            let totalWidth = geometry.size.width
            let doneWidth = segmentWidth(done, total: totalWidth)
            let activeWidth = segmentWidth(active, total: totalWidth)
            let refinedWidth = segmentWidth(refined, total: totalWidth)
            let draftWidth = totalWidth - doneWidth - activeWidth - refinedWidth

            HStack(spacing: 0) {
                if done > 0 {
                    RoundedCornerSegment(corners: [.topLeft, .bottomLeft], radius: 3)
                        .fill(CawnexColors.primary)
                        .frame(width: doneWidth)
                }
                if active > 0 {
                    Rectangle()
                        .fill(CawnexColors.primary.opacity(0.6))
                        .frame(width: activeWidth)
                }
                if refined > 0 {
                    Rectangle()
                        .fill(CawnexColors.primary.opacity(0.33))
                        .frame(width: refinedWidth)
                }
                if draft > 0 {
                    RoundedCornerSegment(corners: [.topRight, .bottomRight], radius: 3)
                        .fill(CawnexColors.primary.opacity(0.13))
                        .frame(width: max(draftWidth, 0))
                }
            }
        }
        .frame(height: 6)
        .background(CawnexColors.primary.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 3))
    }

    private func segmentWidth(_ count: Int, total: CGFloat) -> CGFloat {
        guard self.total > 0 else { return 0 }
        return total * CGFloat(count) / CGFloat(self.total)
    }
}

private struct RoundedCornerSegment: Shape {
    let corners: UIRectCorner
    let radius: CGFloat

    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        PipelineBar(done: 5, active: 3, refined: 4, draft: 6)
            .padding()
    }
}
