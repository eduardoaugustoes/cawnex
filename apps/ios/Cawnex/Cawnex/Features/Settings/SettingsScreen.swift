import SwiftUI

struct SettingsScreen: View {
    @Environment(AppStore.self) private var store

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                // Header
                Text("Settings")
                    .font(CawnexTypography.heading0)
                    .foregroundStyle(CawnexColors.cardForeground)

                // Profile Card
                profileCard

                // Account Section
                accountSection
            }
            .padding(.top, CawnexSpacing.lg)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, 100)
        }
        .background(CawnexColors.background)
    }

    // MARK: - Profile Card

    private var profileCard: some View {
        HStack(spacing: 14) {
            // Avatar with gradient
            ZStack {
                LinearGradient(
                    colors: [Color(hex: 0x7C3AED), Color(hex: 0x9F67FF)],
                    startPoint: .top,
                    endPoint: .bottom
                )
                Text(String((store.currentUser?.name ?? "?").prefix(1)))
                    .font(.system(size: 20, weight: .bold))
                    .foregroundStyle(.white)
            }
            .frame(width: 48, height: 48)
            .clipShape(RoundedRectangle(cornerRadius: 24))

            // Name + plan badge + email
            VStack(alignment: .leading, spacing: 2) {
                Text(store.currentUser?.name ?? "User")
                    .font(CawnexTypography.bodyBold)
                    .foregroundStyle(CawnexColors.cardForeground)

                HStack(spacing: 6) {
                    Text("Pro")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(CawnexColors.primaryLight)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Color(hex: 0x7C3AED).opacity(0.13))
                        .clipShape(RoundedRectangle(cornerRadius: 4))

                    Text(store.currentUser?.email ?? "")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 14))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Account Section

    private var accountSection: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("ACCOUNT")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.5)

            VStack(spacing: 0) {
                settingsRow(icon: "person.2.fill", label: "Team & Tenant")
                divider
                settingsRow(icon: "bell.fill", label: "Notifications")
                divider
                creditsRow
                divider
                settingsRow(icon: "arrow.triangle.branch", label: "Webhooks")
                divider
                settingsRow(icon: "key.fill", label: "API Keys")
            }
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - Row Components

    private func settingsRow(icon: String, label: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundStyle(CawnexColors.cardForeground)
                .frame(width: 20)

            Text(label)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 12))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .frame(height: 52)
    }

    private var creditsRow: some View {
        HStack(spacing: 14) {
            Image(systemName: "creditcard.fill")
                .font(.system(size: 16))
                .foregroundStyle(CawnexColors.cardForeground)
                .frame(width: 20)

            Text("Credits & Billing")
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)

            Text("$247.50 left")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(CawnexColors.success)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(CawnexColors.success.opacity(0.13))
                .clipShape(RoundedRectangle(cornerRadius: 4))

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 12))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .frame(height: 52)
    }

    private var divider: some View {
        Rectangle()
            .fill(CawnexColors.border)
            .frame(height: 1)
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return SettingsScreen()
        .environment(store)
}
