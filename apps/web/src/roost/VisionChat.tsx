import { useEffect, useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import {
  Send, Check, Loader2, FileText, MessageSquare, Pencil, Bird,
} from "lucide-react";
import { api, Project, Vision, VisionMessage } from "@/lib/api";

interface Props {
  project: Project;
}

export function VisionChat({ project }: Props) {
  const [vision, setVision] = useState<Vision | null>(null);
  const [messages, setMessages] = useState<VisionMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [tab, setTab] = useState<"chat" | "doc">("chat");
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { load(); }, [project.id]);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function load() {
    try {
      const v = await api.vision.get(project.id);
      setVision(v);
      setMessages(v.messages || []);
    } catch (e) { console.error(e); }
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;

    const text = input.trim();
    const tempMsg: VisionMessage = {
      id: Date.now(), role: "user", content: text, applied: false, created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, tempMsg]);
    setInput("");
    setSending(true);

    try {
      const resp = await api.vision.chat(project.id, text);
      setMessages(prev => [...prev, resp]);
    } catch (e: any) {
      setMessages(prev => [...prev, {
        id: Date.now(), role: "assistant", content: `❌ ${e.message}`, applied: false, created_at: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  async function applyMessage(msgId: number) {
    try {
      const updated = await api.vision.apply(project.id, msgId);
      setVision(updated);
      setMessages(prev => prev.map(m => m.id === msgId ? { ...m, applied: true } : m));
    } catch (e) { console.error(e); }
  }

  async function saveEdit() {
    try {
      const updated = await api.vision.update(project.id, editContent);
      setVision(updated);
      setEditing(false);
    } catch (e) { console.error(e); }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Tab bar */}
      <div className="px-6 py-3 border-b border-border flex items-center gap-2">
        <button
          onClick={() => setTab("chat")}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm transition-smooth ${
            tab === "chat" ? "bg-crow-dim text-crow" : "text-text-muted hover:text-text hover:bg-bg-surface"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Chat
        </button>
        <button
          onClick={() => setTab("doc")}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm transition-smooth ${
            tab === "doc" ? "bg-crow-dim text-crow" : "text-text-muted hover:text-text hover:bg-bg-surface"
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          Document
          {vision && vision.version > 0 && (
            <span className="text-[10px] text-text-faint">v{vision.version}</span>
          )}
        </button>
      </div>

      {tab === "chat" ? (
        <>
          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 md:px-6 space-y-3">
            {messages.length === 0 && !sending && (
              <div className="flex flex-col items-center justify-center h-full text-center py-16">
                <div className="w-14 h-14 rounded-2xl bg-crow-dim flex items-center justify-center mb-4">
                  <Bird className="w-7 h-7 text-crow" />
                </div>
                <h3 className="text-base font-semibold mb-1">Vision Board</h3>
                <p className="text-sm text-text-muted max-w-xs">
                  Describe what you're building. The AI will help you shape a clear product vision.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-fadeIn`}
              >
                <div className={`max-w-[85%] md:max-w-[70%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-bubble-user border border-border rounded-br-md"
                    : "bg-bubble-ai border border-border rounded-bl-md"
                }`}>
                  {msg.role === "assistant" && (
                    <div className="flex items-center gap-1.5 mb-2">
                      <Bird className="w-3 h-3 text-crow" />
                      <span className="text-[10px] text-crow font-medium">CAWNEX</span>
                    </div>
                  )}
                  <div className="prose prose-sm max-w-none text-sm leading-relaxed">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                  {msg.role === "assistant" && !msg.applied && (
                    <button
                      onClick={() => applyMessage(msg.id)}
                      className="mt-3 flex items-center gap-1.5 text-xs text-ok hover:text-ok transition-smooth bg-ok-dim px-3 py-1.5 rounded-lg"
                    >
                      <Check className="w-3 h-3" />
                      Apply to Vision
                    </button>
                  )}
                  {msg.role === "assistant" && msg.applied && (
                    <div className="mt-2 flex items-center gap-1 text-[10px] text-ok/60">
                      <Check className="w-3 h-3" /> Applied to document
                    </div>
                  )}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start animate-fadeIn">
                <div className="bg-bubble-ai border border-border rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Bird className="w-3 h-3 text-crow" />
                    <span className="text-[10px] text-crow font-medium">CAWNEX</span>
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-text-muted text-sm">
                    <Loader2 className="w-4 h-4 animate-spin text-crow" />
                    Thinking...
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <form onSubmit={send} className="px-4 py-3 md:px-6 border-t border-border bg-bg-raised">
            <div className="flex gap-2 items-center">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Describe your product, refine the vision..."
                disabled={sending}
                className="flex-1 bg-bg-input border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-crow disabled:opacity-40 transition-smooth"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="w-11 h-11 flex items-center justify-center bg-crow hover:bg-crow-hover disabled:opacity-30 disabled:hover:bg-crow text-white rounded-xl transition-smooth shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </form>
        </>
      ) : (
        /* Document tab */
        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs text-text-faint">
                Version {vision?.version || 0}
              </span>
              {!editing ? (
                <button
                  onClick={() => { setEditContent(vision?.content || ""); setEditing(true); }}
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-smooth"
                >
                  <Pencil className="w-3 h-3" /> Edit
                </button>
              ) : (
                <div className="flex gap-2">
                  <button onClick={saveEdit} className="px-3 py-1 text-xs bg-ok text-bg rounded-lg hover:opacity-90 transition-smooth">Save</button>
                  <button onClick={() => setEditing(false)} className="px-3 py-1 text-xs text-text-muted hover:text-text transition-smooth">Cancel</button>
                </div>
              )}
            </div>

            {editing ? (
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full min-h-[60vh] bg-bg-input border border-border rounded-xl p-4 text-sm text-text font-mono focus:outline-none focus:border-crow resize-y transition-smooth"
              />
            ) : vision?.content ? (
              <div className="prose prose-sm max-w-none bg-bg-surface border border-border rounded-2xl p-6">
                <ReactMarkdown>{vision.content}</ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-20 text-text-muted">
                <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" />
                <p className="text-sm">No vision document yet.</p>
                <p className="text-xs mt-1">
                  Switch to Chat to build your vision with AI.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
