const BASE = "/api/v1";
const TENANT = "cawnex-dogfood"; // TODO: dynamic from auth

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-Slug": TENANT,
      ...(opts?.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// === Types ===

export interface Project {
  id: number;
  name: string;
  slug: string;
  status: string;
  config: Record<string, unknown> | null;
  repositories: ProjectRepo[];
  has_vision: boolean;
  milestone_count: number;
  task_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectRepo {
  id: number;
  repository_id: number;
  github_full_name: string;
  role: string | null;
  added_at: string;
}

export interface Vision {
  id: number;
  project_id: number;
  content: string;
  version: number;
  updated_at: string;
  messages: VisionMessage[];
}

export interface VisionMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  applied: boolean;
  created_at: string;
}

export interface Milestone {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  goal: string | null;
  position: number;
  status: string;
  github_milestone_id: number | null;
  task_count: number;
  created_at: string;
  updated_at: string;
}

// === Projects ===

export const api = {
  projects: {
    list: () => request<{ items: Project[]; total: number }>("/projects"),
    get: (id: number) => request<Project>(`/projects/${id}`),
    create: (name: string) =>
      request<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
    update: (id: number, data: Partial<Project>) =>
      request<Project>(`/projects/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/projects/${id}`, { method: "DELETE" }),
    addRepo: (id: number, github_full_name: string, role?: string) =>
      request<ProjectRepo>(`/projects/${id}/repos`, {
        method: "POST",
        body: JSON.stringify({ github_full_name, role }),
      }),
  },

  vision: {
    get: (projectId: number) =>
      request<Vision>(`/projects/${projectId}/vision`),
    update: (projectId: number, content: string) =>
      request<Vision>(`/projects/${projectId}/vision`, {
        method: "PUT",
        body: JSON.stringify({ content }),
      }),
    chat: (projectId: number, message: string) =>
      request<VisionMessage>(`/projects/${projectId}/vision/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      }),
    apply: (projectId: number, messageId: number) =>
      request<Vision>(`/projects/${projectId}/vision/apply`, {
        method: "POST",
        body: JSON.stringify({ message_id: messageId }),
      }),
    messages: (projectId: number) =>
      request<VisionMessage[]>(`/projects/${projectId}/vision/messages`),
  },

  milestones: {
    list: (projectId: number) =>
      request<Milestone[]>(`/projects/${projectId}/milestones`),
    create: (
      projectId: number,
      name: string,
      description?: string,
      goal?: string
    ) =>
      request<Milestone>(`/projects/${projectId}/milestones`, {
        method: "POST",
        body: JSON.stringify({ name, description, goal }),
      }),
    update: (projectId: number, id: number, data: Partial<Milestone>) =>
      request<Milestone>(`/projects/${projectId}/milestones/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (projectId: number, id: number) =>
      request<void>(`/projects/${projectId}/milestones/${id}`, {
        method: "DELETE",
      }),
    reorder: (projectId: number, ids: number[]) =>
      request<Milestone[]>(`/projects/${projectId}/milestones/reorder`, {
        method: "POST",
        body: JSON.stringify({ milestone_ids: ids }),
      }),
  },
};
