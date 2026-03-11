import { useNavigate } from "react-router-dom";
import {
  MessageSquare, Target, ListChecks, GitBranch, Users, Zap,
  ChevronRight, FileText, Plus,
} from "lucide-react";
import { Project } from "@/lib/api";

interface Props {
  project: Project;
  onUpdate: () => void;
}

export function Overview({ project }: Props) {
  const navigate = useNavigate();
  const id = project.id;

  const cards = [
    {
      icon: MessageSquare,
      label: "Vision",
      value: project.has_vision ? "Defined" : "Not started",
      color: project.has_vision ? "text-ok" : "text-text-muted",
      bgColor: project.has_vision ? "bg-ok-dim" : "bg-bg-surface",
      path: "vision",
      action: project.has_vision ? "Continue building" : "Start building",
    },
    {
      icon: Target,
      label: "Milestones",
      value: `${project.milestone_count}`,
      color: "text-crow",
      bgColor: "bg-crow-dim",
      path: "milestones",
      action: "Manage milestones",
    },
    {
      icon: ListChecks,
      label: "Issues",
      value: `${project.task_count}`,
      color: "text-info",
      bgColor: "bg-info-dim",
      path: "issues",
      action: "View issues",
    },
    {
      icon: Users,
      label: "Crows",
      value: "4 ready",
      color: "text-warn",
      bgColor: "bg-warn-dim",
      path: "crows",
      action: "View agents",
    },
    {
      icon: Zap,
      label: "Executions",
      value: "0 running",
      color: "text-text-muted",
      bgColor: "bg-bg-surface",
      path: "executions",
      action: "View runs",
    },
    {
      icon: GitBranch,
      label: "Repos",
      value: `${project.repositories.length}`,
      color: "text-text-secondary",
      bgColor: "bg-bg-surface",
      path: "",
      action: "Manage repos",
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Header */}
      <div className="px-6 py-6 md:px-8 md:py-8 border-b border-border">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <p className="text-sm text-text-muted mt-1">Project workspace</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-3 py-1 rounded-full border ${
              project.status === "active"
                ? "border-ok/30 text-ok bg-ok-dim"
                : "border-warn/30 text-warn bg-warn-dim"
            }`}>
              {project.status}
            </span>
          </div>
        </div>
      </div>

      {/* Cards grid */}
      <div className="px-6 py-6 md:px-8">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {cards.map((card) => (
            <button
              key={card.label}
              onClick={() => navigate(`/roost/${id}/${card.path}`)}
              className="text-left p-4 bg-bg-surface hover:bg-bg-surface-hover border border-border hover:border-border-bright rounded-2xl transition-smooth group animate-fadeIn"
            >
              <div className="flex items-start justify-between mb-3">
                <div className={`w-9 h-9 rounded-xl ${card.bgColor} flex items-center justify-center`}>
                  <card.icon className={`w-4.5 h-4.5 ${card.color}`} />
                </div>
                <ChevronRight className="w-4 h-4 text-text-faint group-hover:text-crow transition-smooth" />
              </div>
              <div className={`text-xl font-bold ${card.color}`}>{card.value}</div>
              <div className="text-xs text-text-muted mt-0.5">{card.label}</div>
            </button>
          ))}
        </div>

        {/* Quick actions */}
        <div className="mt-8">
          <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">Quick Actions</h3>
          <div className="space-y-2">
            {!project.has_vision && (
              <button
                onClick={() => navigate(`/roost/${id}/vision`)}
                className="w-full flex items-center gap-3 p-4 bg-crow-dim border border-crow/20 hover:border-crow/40 rounded-xl transition-smooth group"
              >
                <FileText className="w-5 h-5 text-crow" />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium text-crow">Define your vision</div>
                  <div className="text-xs text-text-muted">Chat with AI to build your product vision</div>
                </div>
                <ChevronRight className="w-4 h-4 text-crow/50 group-hover:text-crow transition-smooth" />
              </button>
            )}
            {project.repositories.length === 0 && (
              <button className="w-full flex items-center gap-3 p-4 bg-bg-surface border border-border hover:border-border-bright rounded-xl transition-smooth group">
                <GitBranch className="w-5 h-5 text-text-muted" />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium">Connect a repository</div>
                  <div className="text-xs text-text-muted">Link your GitHub repos to this project</div>
                </div>
                <Plus className="w-4 h-4 text-text-faint group-hover:text-text transition-smooth" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
