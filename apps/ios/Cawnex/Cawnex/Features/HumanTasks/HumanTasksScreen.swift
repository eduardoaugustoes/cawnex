import SwiftUI

struct HumanTasksScreen: View {
    @State var viewModel: HumanTaskViewModel
    var onBack: () -> Void = {}
    var onTaskTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                navRow

                switch viewModel.listState {
                case .idle, .loading:
                    loadingView
                case .loaded:
                    taskSections
                case .error(let message):
                    errorView(message)
                }
            }
            .padding(.horizontal, CawnexSpacing.lg)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.loadList() }
    }

    // MARK: - Navigation

    private var navRow: some View {
        HStack {
            Button(action: onBack) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(CawnexColors.textPrimary)
            }
            Text("Needs Your Input")
                .font(CawnexTypography.heading2)
                .foregroundColor(CawnexColors.textPrimary)
            Spacer()
            if viewModel.pendingCount > 0 {
                Text("\(viewModel.pendingCount)")
                    .font(CawnexTypography.captionBold)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(CawnexColors.primary)
                    .clipShape(Capsule())
            }
        }
        .padding(.top, CawnexSpacing.md)
    }

    // MARK: - Sections

    private var taskSections: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
            let actionable = (viewModel.taskGroups["notified"] ?? [])
                + (viewModel.taskGroups["in_progress"] ?? [])
                + (viewModel.taskGroups["verification_failed"] ?? [])

            if !actionable.isEmpty {
                sectionHeader("Action Required", count: actionable.count)
                ForEach(actionable) { task in
                    taskCard(task)
                }
            }

            let waiting = (viewModel.taskGroups["responded"] ?? [])
                + (viewModel.taskGroups["verifying"] ?? [])

            if !waiting.isEmpty {
                sectionHeader("Waiting", count: waiting.count)
                ForEach(waiting) { task in
                    taskCard(task)
                }
            }

            let done = viewModel.taskGroups["completed"] ?? []
            if !done.isEmpty {
                sectionHeader("Completed", count: done.count)
                ForEach(done) { task in
                    taskCard(task)
                }
            }
        }
    }

    private func sectionHeader(_ title: String, count: Int) -> some View {
        HStack {
            Text(title)
                .font(CawnexTypography.heading3)
                .foregroundColor(CawnexColors.textPrimary)
            Text("\(count)")
                .font(CawnexTypography.caption)
                .foregroundColor(CawnexColors.textSecondary)
        }
    }

    private func taskCard(_ task: HumanTask) -> some View {
        Button {
            onTaskTap(task.id)
        } label: {
            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                HStack {
                    subtypeIcon(task.subtype)
                    Text(task.ask)
                        .font(CawnexTypography.body)
                        .foregroundColor(CawnexColors.textPrimary)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 14))
                        .foregroundColor(CawnexColors.textTertiary)
                }

                HStack {
                    statusChip(task.status)
                    Spacer()
                    if !task.deadlineHint.isEmpty {
                        Text(task.deadlineHint)
                            .font(CawnexTypography.caption)
                            .foregroundColor(CawnexColors.textTertiary)
                    }
                }
            }
            .padding(CawnexSpacing.lg)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Components

    private func subtypeIcon(_ subtype: String) -> some View {
        let icon: String = switch subtype {
        case "provide_secret": "key.fill"
        case "upload_asset": "arrow.up.doc.fill"
        case "fill_content": "text.alignleft"
        case "configure_ext": "gearshape.fill"
        case "physical_action": "hand.raised.fill"
        case "wait_external": "clock.fill"
        case "confirm": "checkmark.circle.fill"
        default: "questionmark.circle.fill"
        }

        return Image(systemName: icon)
            .font(.system(size: 16))
            .foregroundColor(CawnexColors.primary)
            .frame(width: 28, height: 28)
    }

    private func statusChip(_ status: HumanTaskStatus) -> some View {
        let chipColor: Color = switch status {
        case .notified, .inProgress, .verificationFailed: CawnexColors.primary
        case .responded, .verifying: Color.orange
        case .completed: Color.green
        default: CawnexColors.textTertiary
        }

        return Text(status.displayName)
            .font(CawnexTypography.tiny)
            .foregroundColor(chipColor)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(chipColor.opacity(0.15))
            .clipShape(Capsule())
    }

    // MARK: - States

    private var loadingView: some View {
        VStack(spacing: CawnexSpacing.lg) {
            ProgressView()
                .tint(CawnexColors.primary)
            Text("Loading tasks...")
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: CawnexSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 32))
                .foregroundColor(.red)
            Text(message)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }
}

#Preview {
    HumanTasksScreen(
        viewModel: HumanTaskViewModel(
            humanTaskService: InMemoryHumanTaskService(store: AppStore()),
            projectId: "proj-001"
        )
    )
    .preferredColorScheme(.dark)
}
