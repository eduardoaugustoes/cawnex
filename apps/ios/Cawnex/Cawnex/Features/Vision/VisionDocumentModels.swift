import Foundation

struct DocumentSection: Identifiable, Equatable {
    let id: String
    let title: String
    var content: String
    var status: DocumentSectionStatus
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
    var synthesizedSection: DocumentSection?
}

struct VisionDocumentDetail: Equatable {
    let projectId: String
    let sections: [DocumentSection]
    let messages: [ChatMessage]
}
