import SwiftUI

struct InvestigationTraceScreen: View {
    let vote: AdvisorVote

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                advisorHeader
                Text("INVESTIGATION TIMELINE")
                    .font(.system(size: 11, weight: .semibold))
                    .tracking(0.8)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if vote.investigationTrace.isEmpty {
                    Text("Advisor submitted vote without calling any tools.")
                        .font(.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(CawnexColors.card)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                } else {
                    ForEach(
                        Array(vote.investigationTrace.enumerated()),
                        id: \.element.id
                    ) { idx, call in
                        toolCallRow(index: idx + 1, call: call)
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 20)
        }
        .navigationTitle("\(vote.advisor.displayName) · Investigation")
        .navigationBarTitleDisplayMode(.inline)
    }

    private var advisorHeader: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(CawnexColors.primary.opacity(0.13))
                        .frame(width: 32, height: 32)
                    Image(systemName: vote.advisor.iconName)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(CawnexColors.primary)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(vote.advisor.displayName)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text(
                        "Voted \(vote.vote.chipLabel) · \(String(format: "%.2f", vote.confidence)) confidence"
                    )
                    .font(.caption2)
                    .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                Text(vote.vote.chipLabel)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(vote.vote.chipColor)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(vote.vote.chipColor.opacity(0.13))
                    .clipShape(Capsule())
            }

            Divider().overlay(CawnexColors.border)

            HStack {
                stat("\(vote.investigationTrace.count)", label: "Tool calls")
                Spacer()
                stat(tokenLabel, label: "Tokens")
                Spacer()
                stat(durationLabel, label: "Duration")
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    private func stat(_ value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(CawnexColors.cardForeground)
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private func toolCallRow(index: Int, call: ToolCall) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text("\(index)")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(CawnexColors.cardForeground)
                    .frame(width: 20, height: 20)
                    .background(CawnexColors.muted)
                    .clipShape(Capsule())
                Text(call.toolName)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(CawnexColors.primary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(CawnexColors.primary.opacity(0.13))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                Spacer()
                if let err = call.error {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(CawnexColors.warning)
                        .help(err)
                }
                Text("\(call.durationMs) ms")
                    .font(.caption2)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            if !call.args.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(
                        call.args.sorted(by: { $0.key < $1.key }), id: \.key
                    ) { k, v in
                        HStack(alignment: .top, spacing: 6) {
                            Text("\(k):")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundStyle(CawnexColors.mutedForeground)
                            Text(displayValue(v))
                                .font(.system(size: 11))
                                .foregroundStyle(CawnexColors.cardForeground)
                                .lineLimit(2)
                                .truncationMode(.tail)
                        }
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: 4))
            }
            Text("→ \(call.resultSummary)")
                .font(.system(size: 11))
                .italic()
                .foregroundStyle(CawnexColors.mutedForeground)
                .frame(maxWidth: .infinity, alignment: .leading)
            if let err = call.error {
                Text("⚠️ \(err)")
                    .font(.caption2)
                    .foregroundStyle(CawnexColors.warning)
            }
        }
        .padding(12)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityIdentifier("investigation-trace.tool-call.\(index)")
    }

    private func displayValue(_ value: AnyCodable) -> String {
        guard let v = value.value else { return "null" }
        if let s = v as? String {
            return s.count > 80 ? String(s.prefix(80)) + "…" : s
        }
        return "\(v)"
    }

    private var tokenLabel: String {
        let total = (vote.cost?.tokensIn ?? 0) + (vote.cost?.tokensOut ?? 0)
        if total >= 1000 { return String(format: "%.1fK", Double(total) / 1000.0) }
        return "\(total)"
    }

    private var durationLabel: String {
        let total = vote.investigationTrace.reduce(0) { $0 + $1.durationMs }
        return total > 1000 ? String(format: "%.1fs", Double(total) / 1000.0) : "\(total)ms"
    }
}
