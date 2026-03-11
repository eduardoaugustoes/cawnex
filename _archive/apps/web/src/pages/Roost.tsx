import { useEffect, useState } from "react";
import { useParams, useNavigate, useLocation, Routes, Route } from "react-router-dom";
import {
  Bird, LayoutDashboard, MessageSquare, Target, ListChecks,
  Users, Zap, ArrowLeft, Settings,
} from "lucide-react";
import { api, Project } from "@/lib/api";
import { Overview } from "@/roost/Overview";
import { VisionChat } from "@/roost/VisionChat";
import { Milestones } from "@/roost/Milestones";
import { Issues } from "@/roost/Issues";
import { Crows } from "@/roost/Crows";
import { Executions } from "@/roost/Executions";

const NAV_ITEMS = [
  { path: "", icon: LayoutDashboard, label: "Overview", key: "overview" },
  { path: "vision", icon: MessageSquare, label: "Vision", key: "vision" },
  { path: "milestones", icon: Target, label: "Milestones", key: "milestones" },
  { path: "issues", icon: ListChecks, label: "Issues", key: "issues" },
  { path: "crows", icon: Users, label: "Crows", key: "crows" },
  { path: "executions", icon: Zap, label: "Executions", key: "executions" },
];

export function Roost() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const navigate = useNavigate();
  const location = useLocation();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadProject(); }, [projectId]);

  async function loadProject() {
    try {
      setProject(await api.projects.get(projectId));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  // Determine active nav item
  const pathAfterRoost = location.pathname.replace(`/roost/${id}`, "").replace(/^\//, "");
  const activeKey = NAV_ITEMS.find(n => n.path === pathAfterRoost)?.key || "overview";

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-crow border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="h-screen flex items-center justify-center text-text-muted">
        Project not found
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col md:flex-row">
      {/* Sidebar — desktop */}
      <aside className="hidden md:flex flex-col w-16 lg:w-56 bg-sidebar border-r border-border shrink-0">
        {/* Logo + back */}
        <div className="p-3 lg:px-4 lg:py-4 border-b border-border">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 text-text-muted hover:text-text transition-smooth w-full"
          >
            <ArrowLeft className="w-4 h-4 shrink-0" />
            <span className="hidden lg:inline text-xs">Projects</span>
          </button>
        </div>

        {/* Project name */}
        <div className="p-3 lg:px-4 lg:py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-crow-dim flex items-center justify-center shrink-0">
              <Bird className="w-3.5 h-3.5 text-crow" />
            </div>
            <div className="hidden lg:block min-w-0">
              <div className="text-sm font-semibold truncate">{project.name}</div>
              <div className="text-xs text-text-faint">{project.slug}</div>
            </div>
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-2 space-y-0.5 px-2">
          {NAV_ITEMS.map((item) => {
            const active = activeKey === item.key;
            return (
              <button
                key={item.key}
                onClick={() => navigate(`/roost/${id}${item.path ? `/${item.path}` : ""}`)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-smooth ${
                  active
                    ? "bg-sidebar-active text-crow"
                    : "text-text-muted hover:text-text hover:bg-sidebar-hover"
                }`}
              >
                <item.icon className={`w-4 h-4 shrink-0 ${active ? "text-crow" : ""}`} />
                <span className="hidden lg:inline">{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="p-3 border-t border-border">
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-text-faint hover:text-text-muted transition-smooth">
            <Settings className="w-4 h-4" />
            <span className="hidden lg:inline">Settings</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-h-0 flex flex-col overflow-hidden">
        <Routes>
          <Route index element={<Overview project={project} onUpdate={loadProject} />} />
          <Route path="vision" element={<VisionChat project={project} />} />
          <Route path="milestones" element={<Milestones project={project} onUpdate={loadProject} />} />
          <Route path="issues" element={<Issues project={project} />} />
          <Route path="crows" element={<Crows />} />
          <Route path="executions" element={<Executions />} />
        </Routes>
      </main>

      {/* Bottom nav — mobile */}
      <nav className="md:hidden flex border-t border-border bg-sidebar px-1 py-1 safe-area-bottom">
        {NAV_ITEMS.map((item) => {
          const active = activeKey === item.key;
          return (
            <button
              key={item.key}
              onClick={() => navigate(`/roost/${id}${item.path ? `/${item.path}` : ""}`)}
              className={`flex-1 flex flex-col items-center gap-0.5 py-2 rounded-xl transition-smooth ${
                active ? "text-crow" : "text-text-faint"
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span className="text-[10px]">{item.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
