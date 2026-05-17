import SwiftUI

struct AdvisorCard: View {
    let vote: AdvisorVote
    let onViewInvestigation: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Top row: icon + name (+ VETO badge) + vote chip
            HStack(alignment: .center, spacing: 10) {
                ZStack {
                    Circle()
                        .fill(iconBackground)
                        .frame(width: 28, height: 28)
                    Image(systemName: vote.advisor.iconName)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(iconColor)
                }
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(vote.advisor.displayName)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(CawnexColors.cardForeground)
                        if vote.advisor.hasVeto {
                            vetoBadge
                        }
                    }
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                voteChip
            }

            // Reasoning text
            Text(vote.reasoning)
                .font(.system(size: 13))
                .lineSpacing(2)
                .foregroundStyle(CawnexColors.cardForeground)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Cited evidence (inline, hidden if empty)
            if !vote.citedEvidence.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(vote.citedEvidence) { e in
                        CitedEvidenceRow(evidence: e)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: 4))
            }

            // Veto blockers (only when vote == block)
            if vote.vote == .block && !vote.blockers.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(vote.blockers, id: \.self) { b in
                        Text("• \(b)")
                            .font(.caption)
                            .foregroundStyle(CawnexColors.destructive)
                    }
                }
            }

            // View investigation affordance (hidden when trace is empty)
            if !vote.investigationTrace.isEmpty {
                HStack {
                    Spacer()
                    Button(action: onViewInvestigation) {
                        HStack(spacing: 4) {
                            Text("View investigation")
                                .font(.system(size: 12, weight: .semibold))
                            Image(systemName: "chevron.right")
                                .font(.caption2)
                        }
                        .foregroundStyle(CawnexColors.primary)
                    }
                    .accessibilityIdentifier(
                        "wave-review.advisor.\(vote.advisor.rawValue).view-trace"
                    )
                }
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(borderColor, lineWidth: vote.vote == .block ? 1.5 : 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityIdentifier("wave-review.advisor.\(vote.advisor.rawValue)")
    }

    // MARK: - Derived

    private var subtitle: String {
        let calls = vote.investigationTrace.count
        let conf = String(format: "%.2f", vote.confidence)
        return "\(calls) tool calls · \(conf) conf"
    }

    private var voteChip: some View {
        Text(vote.vote.chipLabel)
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(vote.vote.chipColor)
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(vote.vote.chipColor.opacity(0.13))
            .clipShape(Capsule())
    }

    private var vetoBadge: some View {
        Text("VETO")
            .font(.system(size: 9, weight: .bold))
            .tracking(0.5)
            .foregroundStyle(CawnexColors.primary)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(CawnexColors.primary.opacity(0.13))
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private var iconColor: Color {
        switch vote.advisor {
        case .security, .clarity: CawnexColors.primary
        case .architecture: CawnexColors.info
        case .performance: CawnexColors.warning
        case .ux: CawnexColors.info
        case .cost: CawnexColors.success
        }
    }

    private var iconBackground: Color { iconColor.opacity(0.13) }

    private var borderColor: Color {
        vote.vote == .block ? CawnexColors.destructive : CawnexColors.border
    }
}
