import Foundation
import SwiftUI

// MARK: - Session

struct CouncilSession: Equatable, Codable {
    let sessionId: String
    let waveId: String
    let projectId: String
    let status: CouncilSessionStatus
    let integrationSK: String
    let createdAt: Date
    let completedAt: Date?
    let decision: CouncilDecision?
    let rounds: [VotingRound]
    let cost: AdvisorCost?
    let pipelineHealth: PipelineHealth

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case waveId = "wave_id"
        case projectId = "project_id"
        case status
        case integrationSK = "integration_sk"
        case createdAt = "created_at"
        case completedAt = "completed_at"
        case decision
        case rounds
        case cost
        case pipelineHealth = "pipeline_health"
    }
}

enum CouncilSessionStatus: String, Codable {
    case pending, running, completed, errored
}

enum PipelineHealth: String, Codable {
    case ok, degraded
}

// MARK: - Decision

struct CouncilDecision: Equatable, Codable {
    let action: DecisionAction
    let reasoning: String
    let confidence: Double
    let conditions: [String]
    let orderingConstraints: [String]
    let dissentRecord: [String: String]

    enum CodingKeys: String, CodingKey {
        case action, reasoning, confidence, conditions
        case orderingConstraints = "ordering_constraints"
        case dissentRecord = "dissent_record"
    }
}

enum DecisionAction: String, Codable {
    case approve
    case approveWithConditions = "approve_with_conditions"
    case reject
    case escalate
}

// MARK: - Rounds and votes

struct VotingRound: Equatable, Codable {
    let roundNumber: Int
    let votes: [AdvisorVote]
    let consensus: Bool
    let question: String?

    enum CodingKeys: String, CodingKey {
        case roundNumber = "round_number"
        case votes, consensus, question
    }
}

struct AdvisorVote: Equatable, Codable, Identifiable {
    var id: String { advisor.rawValue }
    let advisor: AdvisorType
    let vote: VoteType
    let reasoning: String
    let confidence: Double
    let blockers: [String]
    let condition: String?
    let citedEvidence: [CitedEvidence]
    let investigationTrace: [ToolCall]
    let cost: AdvisorCost?

    enum CodingKeys: String, CodingKey {
        case advisor, vote, reasoning, confidence, blockers, condition, cost
        case citedEvidence = "cited_evidence"
        case investigationTrace = "investigation_trace"
    }
}

enum AdvisorType: String, Codable, CaseIterable {
    case security, architecture, clarity, performance, ux, cost
}

enum VoteType: String, Codable {
    case approve
    case approveWithCondition = "approve_with_condition"
    case abstain
    case block
}

// MARK: - Evidence and trace

struct CitedEvidence: Equatable, Codable, Identifiable {
    var id: String { "\(filePath):\(lineRange?.first ?? 0)" }
    let filePath: String
    let lineRange: [Int]?
    let prNumber: Int?
    let reason: String

    enum CodingKeys: String, CodingKey {
        case filePath = "file_path"
        case lineRange = "line_range"
        case prNumber = "pr_number"
        case reason
    }
}

struct ToolCall: Equatable, Codable, Identifiable {
    let id: UUID
    let toolName: String
    let args: [String: AnyCodable]
    let resultSummary: String
    let durationMs: Int
    let error: String?

    init(
        id: UUID = UUID(),
        toolName: String,
        args: [String: AnyCodable],
        resultSummary: String,
        durationMs: Int,
        error: String? = nil
    ) {
        self.id = id
        self.toolName = toolName
        self.args = args
        self.resultSummary = resultSummary
        self.durationMs = durationMs
        self.error = error
    }

    enum CodingKeys: String, CodingKey {
        case toolName = "tool_name"
        case args
        case resultSummary = "result_summary"
        case durationMs = "duration_ms"
        case error
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.id = UUID()
        self.toolName = try c.decode(String.self, forKey: .toolName)
        self.args = try c.decode([String: AnyCodable].self, forKey: .args)
        self.resultSummary = try c.decode(String.self, forKey: .resultSummary)
        self.durationMs = try c.decode(Int.self, forKey: .durationMs)
        self.error = try c.decodeIfPresent(String.self, forKey: .error)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(toolName, forKey: .toolName)
        try c.encode(args, forKey: .args)
        try c.encode(resultSummary, forKey: .resultSummary)
        try c.encode(durationMs, forKey: .durationMs)
        try c.encodeIfPresent(error, forKey: .error)
    }

    static func == (lhs: ToolCall, rhs: ToolCall) -> Bool {
        lhs.toolName == rhs.toolName
            && lhs.args == rhs.args
            && lhs.resultSummary == rhs.resultSummary
            && lhs.durationMs == rhs.durationMs
            && lhs.error == rhs.error
    }
}

struct AdvisorCost: Equatable, Codable {
    let tokensIn: Int
    let tokensOut: Int
    let durationMs: Int

    enum CodingKeys: String, CodingKey {
        case tokensIn = "tokens_in"
        case tokensOut = "tokens_out"
        case durationMs = "duration_ms"
    }
}

// MARK: - Display extensions

extension VoteType {
    var chipColor: Color {
        switch self {
        case .approve: CawnexColors.success
        case .approveWithCondition: CawnexColors.warning
        case .abstain: CawnexColors.mutedForeground
        case .block: CawnexColors.destructive
        }
    }

    var chipLabel: String {
        switch self {
        case .approve: "Approve"
        case .approveWithCondition: "Approve w/ condition"
        case .abstain: "Abstained"
        case .block: "Block (Veto)"
        }
    }
}

extension AdvisorType {
    var displayName: String {
        switch self {
        case .security: "Security"
        case .architecture: "Architecture"
        case .clarity: "Clarity"
        case .performance: "Performance"
        case .ux: "UX"
        case .cost: "Cost"
        }
    }

    var iconName: String {
        switch self {
        case .security: "shield.checkered"
        case .architecture: "square.stack.3d.up"
        case .clarity: "eye"
        case .performance: "gauge.medium"
        case .ux: "iphone"
        case .cost: "creditcard"
        }
    }

    var hasVeto: Bool { self == .security || self == .clarity }
}

extension DecisionAction {
    var displayLabel: String {
        switch self {
        case .approve: "Approve"
        case .approveWithConditions: "Approve with conditions"
        case .reject: "Reject"
        case .escalate: "Escalate"
        }
    }

    var displayColor: Color {
        switch self {
        case .approve: CawnexColors.success
        case .approveWithConditions: CawnexColors.warning
        case .reject, .escalate: CawnexColors.destructive
        }
    }
}
