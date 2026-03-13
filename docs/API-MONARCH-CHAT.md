# Monarch Chat API

## Overview

Conversational API for steering AI projects. Each Court has a Monarch that maintains context, consults Council, and provides natural language project management.

## Base URL
```
https://api.cawnex.com/v1
```

## Authentication
```
Authorization: Bearer {user_jwt}
X-Dynasty-ID: {org_id}
```

---

## 📱 Core Endpoints

### **GET /dynasty/{dynasty_id}/courts**
List all projects for the organization.

**Response:**
```json
{
  "courts": [
    {
      "court_id": "cawnex",
      "name": "Cawnex Platform", 
      "directive": "Build Sprint 1: foundation + context",
      "status": "active",
      "current_wave": 2,
      "last_activity": "2026-03-13T21:30:00Z",
      "progress": {
        "tasks_completed": 3,
        "tasks_total": 7,
        "estimated_completion": "2026-03-15T18:00:00Z"
      }
    },
    {
      "court_id": "calhou",
      "name": "Calhou Calculator",
      "directive": "MVP quoting calculator", 
      "status": "active",
      "current_wave": 1,
      "last_activity": "2026-03-13T20:15:00Z",
      "progress": {
        "tasks_completed": 1,
        "tasks_total": 4,
        "estimated_completion": "2026-03-14T16:00:00Z"
      }
    }
  ]
}
```

### **POST /dynasty/{dynasty_id}/court/{court_id}/chat**
Send message to project's Monarch.

**Request:**
```json
{
  "message": "How's the reviewer optimization going?",
  "context_limit": 10  // optional, last N messages
}
```

**Response:**
```json
{
  "chat_id": "chat_abc123",
  "message_id": "msg_xyz789",
  "monarch": {
    "response": "Council is concerned about 183-file context overflow. Quality advisor suggests switching to git diff approach. Security advisor approves. Should I direct Murder to implement diff-based reviews?",
    "status_summary": {
      "current_focus": "Context optimization for reviewer",
      "wave_progress": "3/7 tasks completed",
      "council_sentiment": "cautiously_optimistic",
      "estimated_completion": "2026-03-15T18:00:00Z"
    },
    "actions_needed": [
      {
        "action_id": "approve_diff_approach", 
        "description": "Switch reviewer to git diff instead of full repo",
        "impact": "Reduces context from 183 files to ~5-10 changed files",
        "council_votes": {
          "security": "approve",
          "quality": "approve", 
          "performance": "approve",
          "market": "neutral"
        }
      }
    ]
  },
  "timestamp": "2026-03-13T21:35:00Z"
}
```

### **GET /dynasty/{dynasty_id}/court/{court_id}/chat**
Get conversation history.

**Query params:**
- `limit=20` (default: 50)
- `before={message_id}` (pagination)

**Response:**
```json
{
  "messages": [
    {
      "message_id": "msg_001",
      "sender": "human",
      "content": "Start working on Wave 2",
      "timestamp": "2026-03-13T19:00:00Z"
    },
    {
      "message_id": "msg_002", 
      "sender": "monarch",
      "content": "Wave 2 initiated. Council approved 7 tasks focusing on context optimization...",
      "status_snapshot": { ... },
      "timestamp": "2026-03-13T19:01:00Z"
    }
  ],
  "pagination": {
    "has_more": true,
    "next_before": "msg_xyz"
  }
}
```

---

## 🔄 Action Management

### **POST /dynasty/{dynasty_id}/court/{court_id}/actions/{action_id}/approve**
Approve Monarch's proposed action.

**Request:**
```json
{
  "feedback": "Yes, proceed with diff approach but keep full context as fallback"
}
```

**Response:**
```json
{
  "status": "approved",
  "execution_id": "exec_def456",
  "message": "Directing Murder to implement diff-based reviews with fallback option."
}
```

### **POST /dynasty/{dynasty_id}/court/{court_id}/actions/{action_id}/reject**
Reject Monarch's proposed action.

**Request:**
```json
{
  "reason": "Too risky. Let's optimize the current approach first.",
  "alternative": "Focus on file prioritization instead"
}
```

---

## 📊 Real-time Updates

### **WebSocket: /dynasty/{dynasty_id}/court/{court_id}/stream**
Real-time updates for project activity.

**Events:**
```json
// Monarch message
{
  "type": "monarch_message",
  "chat_id": "chat_abc123", 
  "message": { ... }
}

// Wave progress
{
  "type": "wave_progress",
  "wave_id": 2,
  "tasks_completed": 4,
  "tasks_total": 7,
  "estimated_completion": "2026-03-15T16:30:00Z"
}

// Action required  
{
  "type": "action_required",
  "action": { ... },
  "urgency": "high|medium|low"
}

// Execution updates
{
  "type": "execution_update",
  "execution_id": "exec_123",
  "step": "reviewer",
  "status": "running|completed|failed",
  "details": "Reviewing 3 modified files..."
}
```

---

## 💬 Message Types

### **Human → Monarch**
```json
{
  "type": "directive",          // "Focus on security"
  "type": "question",           // "What's the ETA?" 
  "type": "feedback",           // "Good progress, but..."
  "type": "approval",           // "Yes, proceed"
  "type": "steering"            // "Pivot to mobile-first"
}
```

### **Monarch → Human**
```json
{
  "type": "status_update",      // Regular progress reports
  "type": "council_summary",    // "Council voted to..." 
  "type": "action_request",     // "Should I proceed with X?"
  "type": "problem_alert",      // "Wave 2 blocked by Y"
  "type": "completion_report"   // "Wave completed successfully"
}
```

---

## 🎯 Mobile App Integration

### **Project Card Component**
```swift
struct ProjectCard: View {
    let court: Court
    
    var body: some View {
        VStack(alignment: .leading) {
            HStack {
                Text(court.name)
                Spacer()
                StatusIndicator(court.status)
            }
            
            Text(court.directive)
                .font(.caption)
                .foregroundColor(.secondary)
            
            ProgressBar(completed: court.progress.completed, 
                       total: court.progress.total)
            
            HStack {
                NavigationLink("💬 Chat with Monarch") {
                    MonarchChatView(courtId: court.id)
                }
                .buttonStyle(PrimaryButtonStyle())
                
                Spacer()
                
                Text("Wave \(court.currentWave)")
                    .font(.caption)
            }
        }
        .padding()
        .background(Color.cardBackground)
        .cornerRadius(12)
    }
}
```

### **Chat Interface**
```swift
struct MonarchChatView: View {
    @StateObject private var chatManager = MonarchChatManager()
    @State private var messageText = ""
    
    var body: some View {
        VStack {
            // Status header
            StatusHeaderView(court: chatManager.court)
            
            // Messages
            ScrollView {
                LazyVStack {
                    ForEach(chatManager.messages) { message in
                        MessageBubble(message: message)
                    }
                }
            }
            
            // Actions (when Monarch requests approval)
            if let action = chatManager.pendingAction {
                ActionApprovalView(action: action) { approved in
                    chatManager.handleAction(action.id, approved: approved)
                }
            }
            
            // Input
            HStack {
                TextField("Message Monarch...", text: $messageText)
                Button("Send") {
                    chatManager.sendMessage(messageText)
                    messageText = ""
                }
            }
        }
        .navigationTitle("Monarch - \(chatManager.court.name)")
    }
}
```

---

## 🚀 Implementation Notes

1. **Monarch Context**: Maintains conversation memory + project state
2. **Council Integration**: Auto-consults advisors for decisions
3. **Murder Coordination**: Translates approvals into execution commands
4. **Real-time**: WebSocket for live progress updates
5. **Caching**: Aggressive prompt caching on project context (90% savings)

**Next Steps:**
1. Implement core chat endpoints
2. Add WebSocket streaming
3. Integrate with existing Murder/Crow infrastructure
4. Build iOS chat components