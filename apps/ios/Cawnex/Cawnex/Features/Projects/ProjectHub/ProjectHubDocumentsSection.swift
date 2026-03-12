import SwiftUI

struct ProjectHubDocumentsSection: View {
    let documents: [ProjectDocument]
    let onDocumentTap: (DocumentType) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("DOCUMENTS")
                .font(CawnexTypography.label)
                .tracking(1.5)
                .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: 10) {
                ForEach(documents) { doc in
                    documentCard(doc)
                }
            }
        }
    }

    private func documentCard(_ doc: ProjectDocument) -> some View {
        let accent = accentColor(for: doc.type)
        let hasBorder = doc.status == .draft || doc.status == .inProgress || doc.status == .complete

        return Button {
            onDocumentTap(doc.type)
        } label: {
            VStack(alignment: .leading, spacing: 6) {
                Image(systemName: doc.sfIcon)
                    .font(.system(size: 16))
                    .foregroundStyle(hasBorder ? accent : CawnexColors.mutedForeground)
                    .frame(width: 20, height: 20)

                Text(doc.name)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)

                Text(doc.status.rawValue)
                    .font(.custom("Inter", size: 9).weight(.semibold))
                    .foregroundStyle(chipForeground(for: doc.status))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(chipBackground(for: doc.status))
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(
                        hasBorder ? accent.opacity(0.27) : CawnexColors.border,
                        lineWidth: 1
                    )
            )
        }
        .buttonStyle(.plain)
    }

    private func accentColor(for type: DocumentType) -> Color {
        switch type {
        case .vision: CawnexColors.primary
        case .architecture: CawnexColors.info
        case .glossary: CawnexColors.success
        case .design: CawnexColors.accent
        }
    }

    private func chipForeground(for status: DocumentStatus) -> Color {
        switch status {
        case .draft: CawnexColors.warning
        case .notStarted: CawnexColors.mutedForeground
        case .inProgress: CawnexColors.info
        case .complete: CawnexColors.success
        }
    }

    private func chipBackground(for status: DocumentStatus) -> Color {
        switch status {
        case .draft: CawnexColors.warning.opacity(0.13)
        case .notStarted: CawnexColors.muted
        case .inProgress: CawnexColors.info.opacity(0.13)
        case .complete: CawnexColors.success.opacity(0.13)
        }
    }
}
