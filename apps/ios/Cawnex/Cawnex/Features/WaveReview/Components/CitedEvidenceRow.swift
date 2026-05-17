import SwiftUI

/// Single file:line row inside an AdvisorCard. Renders the file path,
/// optional line range, optional PR number, and a one-line reason.
struct CitedEvidenceRow: View {
    let evidence: CitedEvidence

    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: "doc.text")
                .font(.caption2)
                .foregroundStyle(CawnexColors.mutedForeground)
            Text(label)
                .font(.caption)
                .foregroundStyle(CawnexColors.cardForeground)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var label: String {
        var parts: [String] = [evidence.filePath]
        if let lines = evidence.lineRange, lines.count == 2 {
            parts[0] += ":\(lines[0])-\(lines[1])"
        }
        if !evidence.reason.isEmpty {
            parts.append("— \(evidence.reason)")
        }
        return parts.joined(separator: " ")
    }
}

#Preview {
    VStack(spacing: 8) {
        CitedEvidenceRow(
            evidence: CitedEvidence(
                filePath: "apps/api/foo.py",
                lineRange: [42, 58],
                prNumber: 42,
                reason: "tenant_id filter present"
            ))
        CitedEvidenceRow(
            evidence: CitedEvidence(
                filePath: "apps/ios/Cawnex/Cawnex/Features/PR/PRReviewScreen.swift",
                lineRange: nil,
                prNumber: nil,
                reason: "accessibility id missing"
            ))
    }
    .padding()
    .background(CawnexColors.card)
}
