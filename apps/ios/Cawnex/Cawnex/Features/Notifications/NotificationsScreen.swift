import SwiftUI

struct NotificationsScreen: View {
    @State var viewModel: NotificationViewModel
    var onBack: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                navRow
                filterChips

                if case .loading = viewModel.state {
                    loadingView
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                        .padding(.horizontal, CawnexSpacing.xl)
                }

                if viewModel.data != nil {
                    notificationSections
                }
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.bottom, 100)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load() }
    }

    // MARK: - Nav Row

    private var navRow: some View {
        ZStack {
            Text("Notifications")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)
                .frame(maxWidth: .infinity)

            HStack {
                Button(action: onBack) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                .buttonStyle(.plain)

                Spacer()

                Button {} label: {
                    Text("Mark all read")
                        .font(CawnexTypography.captionMedium)
                        .foregroundStyle(CawnexColors.primaryLight)
                }
                .buttonStyle(.plain)
                .disabled(true)
                .opacity(0.4)
            }
        }
        .padding(.horizontal, CawnexSpacing.xl)
    }

    // MARK: - Filter Chips

    private var filterChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: CawnexSpacing.sm) {
                filterChip(label: "All", filter: .all)
                filterChip(label: "Needs Action", filter: .needsAction)
                filterChip(label: "Updates", filter: .updates)
            }
            .padding(.horizontal, CawnexSpacing.xl)
        }
    }

    private func filterChip(label: String, filter: NotificationFilter) -> some View {
        Button { viewModel.selectFilter(filter) } label: {
            Text(label)
                .font(CawnexTypography.captionBold)
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 6)
                .background(viewModel.selectedFilter == filter ? CawnexColors.primary : CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.pill))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading notifications…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - Sections

    private var notificationSections: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xxl) {
            if viewModel.showNeedsActionSection {
                notificationGroup(
                    label: "NEEDS ACTION",
                    items: viewModel.filteredNeedsAction
                )
            }

            if viewModel.showRecentSection {
                notificationGroup(
                    label: "RECENT",
                    items: viewModel.filteredRecent
                )
            }

            if !viewModel.showNeedsActionSection && !viewModel.showRecentSection {
                Text("No notifications")
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, CawnexSpacing.xxxl)
            }
        }
        .padding(.horizontal, CawnexSpacing.xl)
    }

    private func notificationGroup(label: String, items: [CawnexNotification]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            Text(label)
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1)

            ForEach(items) { notification in
                notificationCard(notification)
            }
        }
    }

    // MARK: - Notification Card

    private func notificationCard(_ notification: CawnexNotification) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            cardTopRow(notification)

            Text(notification.description)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
                .fixedSize(horizontal: false, vertical: true)

            if !notification.actions.isEmpty {
                cardActions(notification.actions)
            }
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(cardBorderColor(for: notification.type), lineWidth: 1)
        )
    }

    private func cardTopRow(_ notification: CawnexNotification) -> some View {
        HStack(spacing: CawnexSpacing.sm) {
            Image(systemName: notification.type.icon)
                .font(.system(size: 14))
                .foregroundStyle(iconColor(for: notification.type))
                .frame(width: 24, height: 24)
                .background(iconColor(for: notification.type).opacity(0.15))
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))

            Text(notification.title)
                .font(CawnexTypography.captionBold)
                .foregroundStyle(CawnexColors.cardForeground)
                .lineLimit(1)

            Spacer()

            Text(notification.timestamp)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private func cardActions(_ actions: [NotificationAction]) -> some View {
        HStack(spacing: CawnexSpacing.sm) {
            ForEach(actions, id: \.rawValue) { action in
                Button {} label: {
                    Text(action.rawValue)
                        .font(CawnexTypography.label)
                        .foregroundStyle(.white)
                        .padding(.horizontal, CawnexSpacing.md)
                        .padding(.vertical, 6)
                        .background(actionButtonColor(for: action))
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                }
                .buttonStyle(.plain)
                .disabled(true)
                .opacity(0.4)
            }
            Spacer()
        }
        .padding(.top, CawnexSpacing.xs)
    }

    // MARK: - Helpers

    private func iconColor(for type: NotificationType) -> Color {
        switch type {
        case .taskApproval: return CawnexColors.primary
        case .mviReady:     return CawnexColors.info
        case .taskFailed:   return CawnexColors.destructive
        case .mviShipped:   return CawnexColors.success
        case .creditsLow:   return CawnexColors.warning
        case .visionReady:  return CawnexColors.primaryLight
        }
    }

    private func cardBorderColor(for type: NotificationType) -> Color {
        switch type {
        case .taskFailed:  return CawnexColors.destructive.opacity(0.4)
        case .creditsLow:  return CawnexColors.warning.opacity(0.4)
        default:           return CawnexColors.border
        }
    }

    private func actionButtonColor(for action: NotificationAction) -> Color {
        switch action {
        case .approve:     return CawnexColors.success
        case .reject:      return CawnexColors.destructive
        case .review:      return CawnexColors.primary
        case .investigate: return CawnexColors.warning
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        NotificationsScreen(
            viewModel: NotificationViewModel(
                notificationService: InMemoryNotificationService()
            )
        )
    }
}
