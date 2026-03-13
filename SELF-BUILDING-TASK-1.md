# Self-Building Task 1: API-backed ProjectService

## 🎯 Goal
Replace `InMemoryProjectService` with `APIProjectService` that connects to real backend, enabling the iOS app to manage actual projects instead of mock data.

## 📋 Acceptance Criteria
- [ ] Create new `APIProjectService` class implementing `ProjectService` protocol
- [ ] All existing `ProjectServiceContractTests` pass with new implementation
- [ ] Add backend API endpoints: `GET/POST /dynasty/{dynastyId}/courts`
- [ ] Integrate with existing POC 6 DynamoDB infrastructure
- [ ] Support creating projects that can execute real tasks via POC 6

## 🏗️ Implementation Plan

### Backend (New API endpoints):
```typescript
// Add to existing Lambda or new API Lambda
GET    /dynasty/{dynastyId}/courts
POST   /dynasty/{dynastyId}/courts
GET    /dynasty/{dynastyId}/court/{courtId}
```

### iOS (Service implementation):
```swift
final class APIProjectService: ProjectService {
    private let httpClient: HTTPClient
    private let dynastyId: String
    
    func listProjects() async throws -> [Project] {
        // GET /dynasty/{dynastyId}/courts -> [Project]
    }
    
    func createProject(name: String, description: String, murders: Set<MurderType>) async throws -> Project {
        // POST /dynasty/{dynastyId}/courts -> Project
        // Should create entry in DynamoDB that POC 6 can use
    }
}
```

### Data Model Integration:
```
iOS Project ←→ DynamoDB DYNASTY#org1 / COURT#projectId
iOS Murder ←→ POC 6 execution infrastructure  
iOS Task ←→ DynamoDB task execution records
```

## ✅ Success Metrics
- iOS app shows real projects (not mock data)
- Projects created in iOS can execute tasks via POC 6  
- All contract tests continue to pass
- POC 6 Murder can see projects created through iOS app

## 🎭 Self-Building Test
After implementation, create a new project via iOS app called "Cawnex API Improvements" and use POC 6 to implement the next service (TaskService API).