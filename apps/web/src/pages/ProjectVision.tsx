import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  ArrowLeft, Send, Check, Pencil, MessageSquare, FileText, Loader2,
} from "lucide-react";
import { api, Project, Vision, VisionMessage } from "@/lib/api";

export function ProjectVision() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [project, setProject] = useState<Project | null>(null);
  const [vision, setVision] = useState<Vision | null>(null);
  const [messages, setMessages] = useState<VisionMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "document">("chat");
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadProject();
    loadVision();
  }, [projectId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadProject() {
    try {
      setProject(await api.projects.get(projectId));
    } catch (e) {
      console.error(e);
    }
  }

  async function loadVision() {
    try {
      const v = await api.vision.get(projectId);
      setVision(v);
      setMessages(v.messages || []);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;

    const userMsg: VisionMessage = {
      id: Date.now(),
      role: "user",
      content: input.trim(),
      applied: false,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      const response = await api.vision.chat(projectId, userMsg.content);
      setMessages((prev) => [...prev, response]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content: `❌ Error: ${e.message}`,
          applied: false,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function handleApply(messageId: number) {
    try {
      const updated = await api.vision.apply(projectId, messageId);
      setVision(updated);
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, applied: true } : m))
      );
    } catch (e: any) {
      console.error("Apply failed:", e);
    }
  }

  async function handleSaveEdit() {
    try {
      const updated = await api.vision.update(projectId, editContent);
      setVision(updated);
      setEditing(false);
    } catch (e: any) {
      console.error("Save failed:", e);
    }
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-96 text-text-dim">
        Loading...
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-57px)] flex flex-col">
      {/* Project Header */}
      <div className="border-b border-border px-6 py-3 flex items-center gap-4">
        <Link to="/" className="text-text-dim hover:text-text transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-lg font-semibold">{project.name}</h1>
          <span className="text-xs text-text-muted">{project.slug}</span>
        </div>
        <div className="ml-auto flex gap-1 bg-surface rounded-lg p-0.5 border border-border">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
              activeTab === "chat"
                ? "bg-primary text-white"
                : "text-text-dim hover:text-text"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Chat
          </button>
          <button
            onClick={() => setActiveTab("document")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
              activeTab === "document"
                ? "bg-primary text-white"
                : "text-text-dim hover:text-text"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Document
          </button>
        </div>
      </div>

      {/* Content */}
      {activeTab === "chat" ? (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center py-20 text-text-muted">
                <MessageSquare className="w-10 h-10 mx-auto mb-3 opacity-50" />
                <p className="text-sm">Start a conversation to build your vision.</p>
                <p className="text-xs mt-1">
                  Describe what you're building and the AI will help you draft a vision document.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[75%] rounded-xl px-4 py-3 text-sm ${
                    msg.role === "user"
                      ? "bg-user-bubble text-text border border-border"
                      : "bg-ai-bubble text-text border border-border"
                  }`}
                >
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>

                  {msg.role === "assistant" && !msg.applied && (
                    <div className="mt-3 pt-2 border-t border-border flex gap-2">
                      <button
                        onClick={() => handleApply(msg.id)}
                        className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors"
                      >
                        <Check className="w-3.5 h-3.5" />
                        Apply to Vision
                      </button>
                    </div>
                  )}
                  {msg.role === "assistant" && msg.applied && (
                    <div className="mt-2 text-xs text-accent/60 flex items-center gap-1">
                      <Check className="w-3 h-3" /> Applied
                    </div>
                  )}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start">
                <div className="bg-ai-bubble border border-border rounded-xl px-4 py-3">
                  <Loader2 className="w-4 h-4 animate-spin text-text-dim" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form
            onSubmit={handleSend}
            className="border-t border-border px-6 py-4 flex gap-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Describe your product, ask for changes, refine the vision..."
              disabled={sending}
              className="flex-1 bg-surface border border-border rounded-lg px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-primary disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="px-4 py-2.5 bg-primary hover:bg-primary-hover disabled:opacity-50 disabled:hover:bg-primary text-white rounded-lg transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      ) : (
        /* Document View */
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs text-text-muted">
                Version {vision?.version || 0} • Updated{" "}
                {vision?.updated_at
                  ? new Date(vision.updated_at).toLocaleString()
                  : "never"}
              </div>
              {!editing ? (
                <button
                  onClick={() => {
                    setEditContent(vision?.content || "");
                    setEditing(true);
                  }}
                  className="flex items-center gap-1 text-xs text-text-dim hover:text-text transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  Edit
                </button>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={handleSaveEdit}
                    className="px-3 py-1 text-xs bg-accent text-background rounded-md hover:bg-accent-hover transition-colors"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditing(false)}
                    className="px-3 py-1 text-xs text-text-dim hover:text-text transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>

            {editing ? (
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full min-h-[60vh] bg-surface border border-border rounded-lg p-4 text-sm text-text font-mono focus:outline-none focus:border-primary resize-y"
              />
            ) : vision?.content ? (
              <div className="prose prose-invert prose-sm max-w-none bg-surface border border-border rounded-lg p-6">
                <ReactMarkdown>{vision.content}</ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-20 text-text-muted">
                <FileText className="w-10 h-10 mx-auto mb-3 opacity-50" />
                <p className="text-sm">No vision document yet.</p>
                <p className="text-xs mt-1">
                  Use the Chat tab to build your vision with AI.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
