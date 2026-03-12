import SwiftUI

struct CawnexNavBar<Trailing: View>: View {
    let title: String
    var backColor: Color = CawnexColors.cardForeground
    var onBack: (() -> Void)?
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack {
            if let onBack {
                Button(action: onBack) {
                    HStack(spacing: 10) {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(backColor)
                        Text(title)
                            .font(CawnexTypography.heading3)
                            .foregroundStyle(CawnexColors.cardForeground)
                    }
                }
                .buttonStyle(.plain)
            } else {
                Text(title)
                    .font(CawnexTypography.heading3)
                    .foregroundStyle(CawnexColors.cardForeground)
            }

            Spacer()

            trailing()
        }
    }
}

extension CawnexNavBar where Trailing == EmptyView {
    init(title: String, backColor: Color = CawnexColors.cardForeground, onBack: (() -> Void)? = nil) {
        self.title = title
        self.backColor = backColor
        self.onBack = onBack
        self.trailing = { EmptyView() }
    }
}

// MARK: - Trailing Helpers

struct NavBarIconButton: View {
    let icon: String
    var color: Color = CawnexColors.mutedForeground
    var action: () -> Void = {}

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundStyle(color)
                .frame(width: 20, height: 20)
        }
        .buttonStyle(.plain)
    }
}

struct NavBarActionButton: View {
    let icon: String
    let label: String
    var action: () -> Void = {}

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 12, weight: .semibold))
                Text(label)
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
}

#Preview("Back + Icon") {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        VStack {
            CawnexNavBar(title: "Cawnex Platform", backColor: CawnexColors.primary, onBack: {}) {
                NavBarIconButton(icon: "rectangle.grid.2x2")
            }
            .padding(.horizontal, CawnexSpacing.xl)
            Spacer()
        }
    }
}

#Preview("Back + Action") {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        VStack {
            CawnexNavBar(title: "Backlog", onBack: {}) {
                NavBarActionButton(icon: "plus", label: "Milestone")
            }
            .padding(.horizontal, CawnexSpacing.xl)
            Spacer()
        }
    }
}
