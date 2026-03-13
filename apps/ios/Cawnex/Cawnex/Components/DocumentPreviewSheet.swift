import SwiftUI

struct DocumentPreviewSheet: View {
    let title: String
    let accentColor: Color
    let sections: [DocumentSection]
    var onDismiss: () -> Void = {}

    private var completedCount: Int {
        sections.filter { $0.status == .complete }.count
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.xxl) {
                    header
                    ForEach(sections) { section in
                        sectionView(section)
                    }
                }
                .padding(.top, CawnexSpacing.lg)
                .padding(.horizontal, CawnexSpacing.xl)
                .padding(.bottom, CawnexSpacing.xxxl)
            }
            .background(CawnexColors.background)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close", action: onDismiss)
                        .foregroundStyle(accentColor)
                }
            }
            .toolbarBackground(CawnexColors.background, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "doc.text.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(accentColor)
                Text(title)
                    .font(CawnexTypography.heading2)
                    .foregroundStyle(CawnexColors.cardForeground)
            }

            Text("\(completedCount) of \(sections.count) sections complete")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)

            Rectangle()
                .fill(CawnexColors.border)
                .frame(height: 1)
        }
    }

    private func sectionView(_ section: DocumentSection) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack(spacing: CawnexSpacing.sm) {
                Circle()
                    .fill(section.status == .complete ? accentColor : CawnexColors.muted)
                    .frame(width: 8, height: 8)
                Text(section.title)
                    .font(CawnexTypography.sectionTitle)
                    .foregroundStyle(CawnexColors.cardForeground)
            }

            if section.status == .complete {
                Text(section.content)
                    .font(CawnexTypography.body)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .lineSpacing(4)
            } else {
                Text("Not yet defined — continue the conversation to fill this section.")
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground.opacity(0.5))
                    .italic()
            }

            Rectangle()
                .fill(CawnexColors.border.opacity(0.4))
                .frame(height: 1)
                .padding(.top, CawnexSpacing.sm)
        }
    }
}

#Preview {
    DocumentPreviewSheet(
        title: "Vision Document",
        accentColor: CawnexColors.primary,
        sections: [
            DocumentSection(id: "1", title: "Problem Statement", content: "Founders waste months building the wrong thing.", status: .complete),
            DocumentSection(id: "2", title: "Target User", content: "Technical founders at pre-seed to seed stage.", status: .complete),
            DocumentSection(id: "3", title: "Core Value Proposition", content: "", status: .pending),
            DocumentSection(id: "4", title: "Key Features", content: "", status: .pending),
        ]
    )
}
