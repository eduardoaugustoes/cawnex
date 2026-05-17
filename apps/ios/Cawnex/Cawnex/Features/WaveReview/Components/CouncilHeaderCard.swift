import SwiftUI

struct CouncilHeaderCard: View {
    let session: CouncilSession

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 10) {
                ZStack {
                    Circle()
                        .fill(decisionColor.opacity(0.13))
                        .frame(width: 32, height: 32)
                    Image(systemName: decisionIcon)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(decisionColor)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("Council: \(decisionLabel)")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(decisionColor)
                    Text(metaLine)
                        .font(.caption2)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
            }

            if let reasoning = session.decision?.reasoning, !reasoning.isEmpty {
                Text(reasoning)
                    .font(.system(size: 13))
                    .lineSpacing(2)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Divider().overlay(CawnexColors.border)

            HStack(alignment: .center) {
                statColumn(value: "\(allVotes.count)", label: "Advisors")
                Spacer()
                statColumn(value: "\(totalToolCalls)", label: "Tool calls")
                Spacer()
                statColumn(value: "\(vetoCount)", label: "Vetoes")
                Spacer()
                statColumn(value: tokenLabel, label: "Tokens")
            }
        }
        .padding(16)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(decisionColor.opacity(0.27), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func statColumn(value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(CawnexColors.cardForeground)
            Text(label)
                .font(.caption2)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Derived

    private var allVotes: [AdvisorVote] {
        session.rounds.flatMap(\.votes)
    }

    private var totalToolCalls: Int {
        allVotes.reduce(0) { $0 + $1.investigationTrace.count }
    }

    private var vetoCount: Int {
        allVotes.filter { $0.advisor.hasVeto && $0.vote == .block }.count
    }

    private var tokenLabel: String {
        let total = (session.cost?.tokensIn ?? 0) + (session.cost?.tokensOut ?? 0)
        if total >= 1000 {
            return String(format: "%.1fK", Double(total) / 1000.0)
        }
        return "\(total)"
    }

    private var decisionLabel: String {
        session.decision?.action.displayLabel ?? "—"
    }

    private var decisionColor: Color {
        session.decision?.action.displayColor ?? CawnexColors.mutedForeground
    }

    private var decisionIcon: String {
        switch session.decision?.action {
        case .approve, .approveWithConditions: return "shield.checkered"
        case .reject: return "xmark.shield"
        case .escalate: return "exclamationmark.shield"
        case nil: return "questionmark.circle"
        }
    }

    private var metaLine: String {
        let voted = allVotes.count
        let rounds = session.rounds.count
        let conf = session.decision.map { String(format: "%.2f", $0.confidence) } ?? "—"
        return "\(voted)/6 voted · \(rounds) round\(rounds == 1 ? "" : "s") · \(conf) confidence"
    }
}
