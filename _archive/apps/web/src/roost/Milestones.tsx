import { useEffect, useState } from "react";
import { Target, Plus, GripVertical, Check, Clock, Play, Trash2 } from "lucide-react";
import { api, Project, Milestone } from "@/lib/api";

interface Props {
  project: Project;
  onUpdate: () => void;
}

const STATUS_CONFIG: Record<string, { icon: typeof Clock; color: string; bg: string }> = {
  planned: { icon: Clock, color: "text-text-muted", bg: "bg-bg-surface" },
  active: { icon: Play, color: "text-crow", bg: "bg-crow-dim" },
  completed: { icon: Check, color: "text-ok", bg: "bg-ok-dim" },
};

export function Milestones({ project, onUpdate }: Props) {
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", goal: "" });

  useEffect(() => { load(); }, [project.id]);

  async function load() {
    try {
      setMilestones(await api.milestones.list(project.id));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    try {
      await api.milestones.create(project.id, form.name, form.description || undefined, form.goal || undefined);
      setForm({ name: "", description: "", goal: "" });
      setCreating(false);
      load();
      onUpdate();
    } catch (e) { console.error(e); }
  }

  async function updateStatus(m: Milestone, status: string) {
    try {
      await api.milestones.update(project.id, m.id, { status } as any);
      load();
    } catch (e) { console.error(e); }
  }

  async function remove(m: Milestone) {
    if (!confirm(`Delete milestone "${m.name}"?`)) return;
    try {
      await api.milestones.delete(project.id, m.id);
      load();
      onUpdate();
    } catch (e) { console.error(e); }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-6 py-6 md:px-8 border-b border-border flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">Milestones</h2>
          <p className="text-xs text-text-muted mt-0.5">Define phases and track progress</p>
        </div>
        <button
          onClick={() => setCreating(!creating)}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-crow hover:bg-crow-hover text-white rounded-xl text-sm font-medium transition-smooth"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Add</span>
        </button>
      </div>

      <div className="px-6 py-6 md:px-8 space-y-3">
        {creating && (
          <form onSubmit={create} className="p-4 bg-bg-surface border border-border rounded-2xl space-y-3 animate-fadeIn">
            <input
              autoFocus
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              placeholder="Milestone name"
              className="w-full bg-bg-input border border-border rounded-xl px-4 py-2.5 text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-crow transition-smooth"
            />
            <input
              value={form.goal}
              onChange={e => setForm({ ...form, goal: e.target.value })}
              placeholder="Goal (optional)"
              className="w-full bg-bg-input border border-border rounded-xl px-4 py-2.5 text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-crow transition-smooth"
            />
            <textarea
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder="Description (optional)"
              rows={2}
              className="w-full bg-bg-input border border-border rounded-xl px-4 py-2.5 text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-crow resize-none transition-smooth"
            />
            <div className="flex gap-2">
              <button type="submit" className="px-4 py-2 bg-crow hover:bg-crow-hover text-white rounded-xl text-sm transition-smooth">Create</button>
              <button type="button" onClick={() => setCreating(false)} className="px-4 py-2 text-text-muted hover:text-text rounded-xl text-sm transition-smooth">Cancel</button>
            </div>
          </form>
        )}

        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-crow border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && milestones.length === 0 && !creating && (
          <div className="text-center py-16">
            <Target className="w-10 h-10 text-text-faint mx-auto mb-3" />
            <p className="text-sm text-text-muted">No milestones yet</p>
            <p className="text-xs text-text-faint mt-1">Define phases to organize your work</p>
          </div>
        )}

        {milestones.map((m, i) => {
          const cfg = STATUS_CONFIG[m.status] || STATUS_CONFIG.planned;
          const StatusIcon = cfg.icon;
          return (
            <div
              key={m.id}
              className="p-4 bg-bg-surface border border-border hover:border-border-bright rounded-2xl transition-smooth group animate-fadeIn"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-start gap-3">
                <div className={`w-9 h-9 rounded-xl ${cfg.bg} flex items-center justify-center shrink-0 mt-0.5`}>
                  <StatusIcon className={`w-4 h-4 ${cfg.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold">{m.name}</h3>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                      {m.status}
                    </span>
                  </div>
                  {m.goal && <p className="text-xs text-text-secondary mt-1">🎯 {m.goal}</p>}
                  {m.description && <p className="text-xs text-text-muted mt-1">{m.description}</p>}
                  <div className="flex items-center gap-3 mt-2 text-xs text-text-faint">
                    <span>{m.task_count} issue{m.task_count !== 1 ? "s" : ""}</span>
                    <span>pos {m.position}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-smooth">
                  {m.status === "planned" && (
                    <button onClick={() => updateStatus(m, "active")} className="p-1.5 hover:bg-crow-dim rounded-lg transition-smooth" title="Start">
                      <Play className="w-3.5 h-3.5 text-crow" />
                    </button>
                  )}
                  {m.status === "active" && (
                    <button onClick={() => updateStatus(m, "completed")} className="p-1.5 hover:bg-ok-dim rounded-lg transition-smooth" title="Complete">
                      <Check className="w-3.5 h-3.5 text-ok" />
                    </button>
                  )}
                  <button onClick={() => remove(m)} className="p-1.5 hover:bg-bad-dim rounded-lg transition-smooth" title="Delete">
                    <Trash2 className="w-3.5 h-3.5 text-bad" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
