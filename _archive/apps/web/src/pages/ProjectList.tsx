import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Bird, ChevronRight, GitBranch, Target, ListChecks } from "lucide-react";
import { api, Project } from "@/lib/api";

const STATUS_STYLE: Record<string, { dot: string; text: string }> = {
  draft: { dot: "bg-warn", text: "text-warn" },
  active: { dot: "bg-ok", text: "text-ok" },
  paused: { dot: "bg-text-muted", text: "text-text-muted" },
  archived: { dot: "bg-text-faint", text: "text-text-faint" },
};

export function ProjectList() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  useEffect(() => { loadProjects(); }, []);

  async function loadProjects() {
    try {
      const data = await api.projects.list();
      setProjects(data.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      const p = await api.projects.create(newName.trim());
      setNewName("");
      setCreating(false);
      navigate(`/roost/${p.id}`);
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero header */}
      <header className="border-b border-border px-6 py-5 md:px-10 md:py-8">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-crow-dim flex items-center justify-center">
              <Bird className="w-5 h-5 text-crow" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Cawnex</h1>
              <p className="text-xs text-text-muted">Coordinated Intelligence</p>
            </div>
          </div>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-crow hover:bg-crow-hover text-white rounded-xl text-sm font-medium transition-smooth"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New Project</span>
          </button>
        </div>
      </header>

      <main className="flex-1 px-6 md:px-10 py-8">
        <div className="max-w-5xl mx-auto">
          {/* Create dialog */}
          {creating && (
            <div className="mb-8 animate-fadeIn">
              <form onSubmit={handleCreate} className="p-5 bg-bg-surface border border-border rounded-2xl">
                <label className="text-sm text-text-secondary block mb-2">Project name</label>
                <div className="flex gap-3">
                  <input
                    autoFocus
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. Cawnex Platform"
                    className="flex-1 bg-bg-input border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-crow transition-smooth"
                  />
                  <button type="submit" className="px-6 py-3 bg-crow hover:bg-crow-hover text-white rounded-xl text-sm font-medium transition-smooth">
                    Create
                  </button>
                  <button type="button" onClick={() => { setCreating(false); setNewName(""); }}
                    className="px-4 py-3 text-text-muted hover:text-text rounded-xl text-sm transition-smooth">
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-32">
              <div className="w-8 h-8 border-2 border-crow border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {/* Empty state */}
          {!loading && projects.length === 0 && !creating && (
            <div className="text-center py-32 animate-fadeIn">
              <div className="w-20 h-20 rounded-2xl bg-crow-dim flex items-center justify-center mx-auto mb-6">
                <Bird className="w-10 h-10 text-crow" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Hatch your first project</h2>
              <p className="text-text-muted text-sm mb-8 max-w-sm mx-auto">
                Create a project to start building your product vision with AI and let the crows do the work.
              </p>
              <button
                onClick={() => setCreating(true)}
                className="px-6 py-3 bg-crow hover:bg-crow-hover text-white rounded-xl text-sm font-medium transition-smooth"
              >
                Create Project
              </button>
            </div>
          )}

          {/* Project cards */}
          {!loading && projects.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wider mb-4">
                Your Projects
              </h2>
              {projects.map((project, i) => {
                const s = STATUS_STYLE[project.status] || STATUS_STYLE.draft;
                return (
                  <button
                    key={project.id}
                    onClick={() => navigate(`/roost/${project.id}`)}
                    className="w-full text-left p-5 bg-bg-surface hover:bg-bg-surface-hover border border-border hover:border-border-bright rounded-2xl transition-smooth group animate-fadeIn"
                    style={{ animationDelay: `${i * 50}ms` }}
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-base font-semibold truncate group-hover:text-crow transition-smooth">
                            {project.name}
                          </h3>
                          <div className="flex items-center gap-1.5">
                            <div className={`w-2 h-2 rounded-full ${s.dot}`} />
                            <span className={`text-xs ${s.text}`}>{project.status}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-text-muted">
                          {project.repositories.length > 0 && (
                            <span className="flex items-center gap-1">
                              <GitBranch className="w-3 h-3" />
                              {project.repositories.length}
                            </span>
                          )}
                          {project.milestone_count > 0 && (
                            <span className="flex items-center gap-1">
                              <Target className="w-3 h-3" />
                              {project.milestone_count}
                            </span>
                          )}
                          {project.task_count > 0 && (
                            <span className="flex items-center gap-1">
                              <ListChecks className="w-3 h-3" />
                              {project.task_count}
                            </span>
                          )}
                          {project.has_vision && (
                            <span className="text-crow text-xs">✦ vision</span>
                          )}
                        </div>
                      </div>
                      <ChevronRight className="w-5 h-5 text-text-faint group-hover:text-crow transition-smooth" />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
