import SwiftUI

struct CawnexTabBar: View {
    @Binding var selectedTab: CawnexTab
    @Namespace private var pillNamespace

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 4) {
                ForEach(CawnexTab.allCases, id: \.self) { tab in
                    tabItem(tab)
                }
            }
            .padding(4)
            .frame(height: 62)
            .background(
                Capsule()
                    .fill(.ultraThinMaterial)
                    .environment(\.colorScheme, .dark)
            )
            .clipShape(Capsule())
            // Depth border: top highlight + bottom shadow
            .overlay(
                Capsule()
                    .strokeBorder(
                        LinearGradient(
                            colors: [
                                Color.white.opacity(0.08),
                                Color.white.opacity(0.03),
                                Color.black.opacity(0.2)
                            ],
                            startPoint: .top,
                            endPoint: .bottom
                        ),
                        lineWidth: 1
                    )
            )
            // Subtle outer glow for lift
            .shadow(color: CawnexColors.primary.opacity(0.08), radius: 12, y: 4)
            .shadow(color: Color.black.opacity(0.3), radius: 8, y: 2)
        }
        .padding(.horizontal, 21)
        .padding(.top, 12)
        .padding(.bottom, 21)
    }

    private func tabItem(_ tab: CawnexTab) -> some View {
        let isSelected = selectedTab == tab

        return Button {
            selectedTab = tab
        } label: {
            VStack(spacing: 4) {
                Group {
                    if tab.isCustomIcon {
                        Image(tab.icon)
                            .renderingMode(.template)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                    } else {
                        Image(systemName: tab.icon)
                    }
                }
                .frame(width: 18, height: 18)
                Text(tab.label)
                    .font(CawnexTypography.display(10, weight: isSelected ? .semibold : .medium))
                    .tracking(0.5)
            }
            .foregroundStyle(isSelected ? CawnexColors.primaryForeground : CawnexColors.mutedForeground)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(
                Group {
                    if isSelected {
                        RoundedRectangle(cornerRadius: 26)
                            .fill(CawnexColors.primaryLight)
                            .matchedGeometryEffect(id: "pill", in: pillNamespace)
                    }
                }
                .animation(.spring(response: 0.35, dampingFraction: 0.7), value: selectedTab)
            )
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        VStack {
            Spacer()
            CawnexTabBar(selectedTab: .constant(.projects))
        }
    }
}

#Preview("Interactive") {
    struct InteractivePreview: View {
        @State private var tab: CawnexTab = .projects
        var body: some View {
            ZStack {
                CawnexColors.background.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 16) {
                        ForEach(0..<20) { i in
                            RoundedRectangle(cornerRadius: 12)
                                .fill(CawnexColors.card)
                                .frame(height: 80)
                                .overlay(Text("Card \(i)").foregroundStyle(.white))
                        }
                    }
                    .padding()
                    .padding(.bottom, 100)
                }
                VStack {
                    Spacer()
                    CawnexTabBar(selectedTab: $tab)
                }
            }
        }
    }
    return InteractivePreview()
}
