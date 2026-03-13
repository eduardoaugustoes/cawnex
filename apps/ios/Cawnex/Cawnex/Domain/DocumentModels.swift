import Foundation

struct DocumentSection: Identifiable, Equatable {
    let id: String
    let title: String
    let content: String
    let status: DocumentSectionStatus
}

enum DocumentSectionStatus: String, Equatable {
    case pending, complete
}

enum ChatRole: String, Equatable {
    case ai, user
}

struct ChatMessage: Identifiable, Equatable {
    let id: String
    let role: ChatRole
    let content: String
    let synthesizedSection: DocumentSection?
}

struct DocumentDetail: Equatable {
    let projectId: String
    let sections: [DocumentSection]
    let messages: [ChatMessage]
}
