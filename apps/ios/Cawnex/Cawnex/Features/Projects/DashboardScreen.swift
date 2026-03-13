import SwiftUI

struct DashboardScreen: View {
    let userName: String
    @State var viewModel: DashboardViewModel
    var onBellTap: () -> Void = {}
    var onAddTap: () -> Void = {}
    var onProjectTap: (Project) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xxl) {
                header
                projectsSection
            }
            .padding(.top, CawnexSpacing.lg)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, 100)
        }
        .task { await viewModel.load() }
        .background(CawnexColors.background)
        .toolbarBackground(CawnexColors.background, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(greeting)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
                Text(userName)
                    .font(CawnexTypography.heading1)
                    .foregroundStyle(CawnexColors.cardForeground)
            }

            Spacer()

            HStack(spacing: CawnexSpacing.md) {
                circleButton(icon: "bell", fill: CawnexColors.card, action: onBellTap)
                circleButton(icon: "plus", fill: CawnexColors.primaryLight, action: onAddTap)
            }
        }
    }

    // MARK: - Projects Section

    private var projectsSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            projectsSectionHeader
            ForEach(viewModel.projects) { project in
                ProjectCard(project: project) {
                    onProjectTap(project)
                }
            }
        }
    }

    private var projectsSectionHeader: some View {
        HStack {
            Text("Your Projects")
                .font(CawnexTypography.sectionTitle)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            HStack(spacing: CawnexSpacing.md) {
                Button {} label: {
                    Image(systemName: "arrow.up.arrow.down")
                        .font(.system(size: 16))
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                .disabled(true)
                .opacity(0.4)
                Button {} label: {
                    Image(systemName: "slider.horizontal.3")
                        .font(.system(size: 16))
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                .disabled(true)
                .opacity(0.4)
            }
        }
    }

    // MARK: - Helpers

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<12: return "Good morning"
        case 12..<18: return "Good afternoon"
        default: return "Good evening"
        }
    }

    private func circleButton(icon: String, fill: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundStyle(.white)
                .frame(width: 40, height: 40)
                .background(fill)
                .clipShape(Circle())
        }
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        DashboardScreen(
            userName: "Eduardo",
            viewModel: {
                let store = AppStore()
                store.seedData()
                return DashboardViewModel(
                    projectService: InMemoryProjectService(store: store)
                )
            }()
        )
    }
}
