import { useEffect, useState } from "react";
import { Bird, Cpu, Wrench, Shield, FileText, Loader2 } from "lucide-react";

interface Agent {
  id: number;
  name: string;
  slug: string;
  description: string;
  model: string;
  tool_packs: string[];
  is_active: boolean;
}

const AGENT_ICONS: Record<string, typeof Bird> = {
  refinement: Shield,
  developer: Cpu,
  reviewer: Wrench,
  documenter: FileText,
};

const AGENT_COLORS: Record<string, { text: string; bg: string }> = {
  refinement: { text: "text-info", bg: "bg-info-dim" },
  developer: { text: "text-crow", bg: "bg-crow-dim" },
  reviewer: { text: "text-warn", bg: "bg-warn-dim" },
  documenter: { text: "text-ok", bg: "bg-ok-dim" },
};

export function Crows() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      const res = await fetch("/api/v1/agents", {
        headers: { "X-Tenant-Slug": "cawnex-dogfood" },
      });
      if (res.ok) {
        const data = await res.json();
        setAgents(data.items || data);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-6 py-6 md:px-8 border-b border-border">
        <h2 className="text-lg font-bold">Crows</h2>
        <p className="text-xs text-text-muted mt-0.5">Your AI agents — the murder</p>
      </div>

      <div className="px-6 py-6 md:px-8">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-crow border-t-transparent rounded-full animate-spin" />
          </div>
        ) : agents.length === 0 ? (
          <div className="text-center py-16">
            <Bird className="w-10 h-10 text-text-faint mx-auto mb-3" />
            <p className="text-sm text-text-muted">No agents found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agents.map((agent, i) => {
              const Icon = AGENT_ICONS[agent.slug] || Bird;
              const colors = AGENT_COLORS[agent.slug] || { text: "text-text-muted", bg: "bg-bg-surface" };
              return (
                <div
                  key={agent.id}
                  className="p-5 bg-bg-surface border border-border hover:border-border-bright rounded-2xl transition-smooth animate-fadeIn"
                  style={{ animationDelay: `${i * 80}ms` }}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center shrink-0`}>
                      <Icon className={`w-5 h-5 ${colors.text}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold">{agent.name}</h3>
                        <div className={`w-2 h-2 rounded-full ${agent.is_active ? "bg-ok" : "bg-text-faint"}`} />
                      </div>
                      <p className="text-xs text-text-muted mb-3">{agent.description}</p>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[10px] px-2 py-0.5 bg-bg-overlay border border-border rounded-md text-text-faint">
                          {agent.model}
                        </span>
                        {agent.tool_packs.map(t => (
                          <span key={t} className="text-[10px] px-2 py-0.5 bg-bg-overlay border border-border rounded-md text-text-faint">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
