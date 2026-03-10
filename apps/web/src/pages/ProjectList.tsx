import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, FolderOpen, GitBranch, Milestone as MilestoneIcon, ListTodo } from "lucide-react";
import { api, Project } from "@/lib/api";

export function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    try {
      const data = await api.projects.list();
      setProjects(data.items);
    } catch (e) {
      console.error("Failed to load projects:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      await api.projects.create(newName.trim());
      setNewName("");
      setCreating(false);
      loadProjects();
    } catch (e) {
      console.error("Failed to create project:", e);
    }
  }

  const statusColors: Record<string, string> = {
    draft: "text-warning",
    active: "text-accent",
    paused: "text-text-dim",
    archived: "text-text-muted",
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-text-dim text-sm mt-1">Your product visions and milestones</p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Create form */}
      {creating && (
        <form onSubmit={handleCreate} className="mb-6 p-4 bg-surface border border-border rounded-lg flex gap-3">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Project name..."
            className="flex-1 bg-background border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-primary"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-md text-sm font-medium transition-colors"
          >
            Create
          </button>
          <button
            type="button"
            onClick={() => { setCreating(false); setNewName(""); }}
            className="px-4 py-2 text-text-dim hover:text-text rounded-md text-sm transition-colors"
          >
            Cancel
          </button>
        </form>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-20 text-text-dim">Loading projects...</div>
      )}

      {/* Empty state */}
      {!loading && projects.length === 0 && !creating && (
        <div className="text-center py-20">
          <FolderOpen className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <h2 className="text-lg font-medium text-text-dim mb-2">No projects yet</h2>
          <p className="text-text-muted text-sm mb-6">Create your first project to start building with AI</p>
          <button
            onClick={() => setCreating(true)}
            className="px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors"
          >
            Create Project
          </button>
        </div>
      )}

      {/* Project cards */}
      <div className="grid gap-3">
        {projects.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="block p-5 bg-surface hover:bg-surface-hover border border-border hover:border-border-bright rounded-lg transition-all group"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold group-hover:text-primary transition-colors">
                  {project.name}
                </h3>
                <div className="flex items-center gap-4 mt-2 text-sm text-text-dim">
                  <span className={statusColors[project.status] || "text-text-dim"}>
                    {project.status}
                  </span>
                  {project.repositories.length > 0 && (
                    <span className="flex items-center gap-1">
                      <GitBranch className="w-3.5 h-3.5" />
                      {project.repositories.length} repo{project.repositories.length !== 1 && "s"}
                    </span>
                  )}
                  {project.milestone_count > 0 && (
                    <span className="flex items-center gap-1">
                      <MilestoneIcon className="w-3.5 h-3.5" />
                      {project.milestone_count} milestone{project.milestone_count !== 1 && "s"}
                    </span>
                  )}
                  {project.task_count > 0 && (
                    <span className="flex items-center gap-1">
                      <ListTodo className="w-3.5 h-3.5" />
                      {project.task_count} task{project.task_count !== 1 && "s"}
                    </span>
                  )}
                </div>
              </div>
              {project.has_vision && (
                <span className="text-xs px-2 py-0.5 bg-accent/10 text-accent rounded-full">
                  has vision
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
