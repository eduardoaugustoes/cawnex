"""The Murder — orchestrator that runs workflow pipelines.

Reads tasks from Redis Stream, executes workflow steps via CrowRunner,
records events/results to the database, and creates PRs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from cawnex_core.enums import TaskStatus, ExecutionStatus, EventType
from cawnex_core.models import (
    Task, Workflow, WorkflowStep, Execution, ExecutionEvent,
    AgentDefinition, Tenant, LLMConfig, Repository,
)
from cawnex_git_ops import GitHubAPI
from cawnex_worker.crows.runner import CrowRunner, CrowResult
from cawnex_worker.crows.subscription_runner import HybridRunner
from cawnex_worker.git_workflow import (
    ensure_repo_cloned, create_task_branch, commit_and_push,
    create_pull_request, update_issue_status, cleanup_nest,
)

logger = logging.getLogger("cawnex.murder")


class Murder:
    """The Murder — coordinates crows through workflow pipelines."""

    def __init__(
        self,
        database_url: str,
        redis_url: str,
        fernet_key: str,
        github_token: str | None = None,
        use_subscription: bool = False,
        claude_cmd: str | None = None,
    ) -> None:
        self.engine = create_async_engine(database_url, pool_size=5)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.fernet_key = fernet_key.encode() if fernet_key else None
        self.github_token = github_token
        self.use_subscription = use_subscription
        self.claude_cmd = claude_cmd
        self._running = False

    async def start(self) -> None:
        """Start consuming tasks from the Redis Stream."""
        self._running = True
        logger.info("🐦‍⬛ The Murder is awake. Listening for tasks...")

        # Create consumer group if needed
        try:
            await self.redis.xgroup_create("cawnex:tasks", "murder", id="0", mkstream=True)
        except Exception:
            pass  # Group already exists

        while self._running:
            try:
                # Read from stream with consumer group
                messages = await self.redis.xreadgroup(
                    groupname="murder",
                    consumername="murder-1",
                    streams={"cawnex:tasks": ">"},
                    count=1,
                    block=5000,
                )

                if not messages:
                    continue

                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        task_id = int(data["task_id"])
                        tenant_id = int(data["tenant_id"])

                        logger.info(f"📋 Picked up task {task_id} (tenant {tenant_id})")

                        try:
                            await self.execute_task(task_id, tenant_id)
                        except Exception as e:
                            logger.error(f"💀 Task {task_id} failed: {e}", exc_info=True)

                        # Acknowledge
                        await self.redis.xack("cawnex:tasks", "murder", msg_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False
        await self.redis.aclose()
        await self.engine.dispose()

    async def execute_task(self, task_id: int, tenant_id: int) -> None:
        """Execute a full workflow pipeline for a task.

        Full lifecycle:
        1. Load task, tenant, workflow from DB
        2. Clone/update the target repository
        3. Create a feature branch (cawnex/issue-{n})
        4. Run each workflow step (agent) against the workspace
        5. Commit changes and push the branch
        6. Create a pull request on GitHub
        7. Update the GitHub issue with status
        """
        workspace = None
        branch_name = None
        step_summaries: list[dict] = []

        async with self.session_factory() as db:
            # ── 1. Load task + tenant + workflow ──
            task = (await db.execute(
                select(Task)
                .where(Task.id == task_id)
                .options(selectinload(Task.workflow))
            )).scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found")
                return

            tenant = (await db.execute(
                select(Tenant)
                .where(Tenant.id == tenant_id)
                .options(selectinload(Tenant.llm_config))
            )).scalar_one()

            # Resolve LLM credentials
            api_key = None
            if not self.use_subscription:
                api_key = self._decrypt_api_key(tenant.llm_config)
                if not api_key:
                    logger.error(f"No API key for tenant {tenant.slug}")
                    task.status = TaskStatus.FAILED
                    await db.commit()
                    return

            workflow = task.workflow
            if not workflow:
                logger.warning(f"Task {task_id} has no workflow")
                task.status = TaskStatus.FAILED
                await db.commit()
                return

            steps = (await db.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id == workflow.id)
                .options(selectinload(WorkflowStep.agent))
                .order_by(WorkflowStep.order)
            )).scalars().all()

            repo_full_name = (task.context or {}).get("repository", "")
            issue_number = (task.context or {}).get("issue_number")
            github_token = self.github_token

            # ── 2. Clone/update repo ──
            task.status = TaskStatus.IN_PROGRESS
            await db.commit()

            if repo_full_name and github_token:
                try:
                    repo_dir = ensure_repo_cloned(repo_full_name, github_token)
                    workspace, branch_name = create_task_branch(
                        repo_dir, task_id, issue_number
                    )

                    # Update issue with "in progress" label
                    if issue_number:
                        gh = GitHubAPI(github_token)
                        await update_issue_status(
                            gh, repo_full_name, issue_number,
                            labels=["cawnex:in-progress"],
                            comment="🐦‍⬛ Cawnex picked this up. The murder is working on it..."
                        )
                        await gh.close()

                except Exception as e:
                    logger.error(f"Git setup failed: {e}", exc_info=True)
                    task.status = TaskStatus.FAILED
                    await db.commit()
                    return
            else:
                # No repo — use tempdir
                import tempfile
                workspace_path = tempfile.mkdtemp(prefix=f"cawnex-task-{task_id}-")
                workspace = __import__("pathlib").Path(workspace_path)

            # ── 3. Load vision context for richer prompts ──
            vision_context = ""
            if task.project_id:
                from cawnex_core.models.project import Project, Vision
                project = (await db.execute(
                    select(Project)
                    .where(Project.id == task.project_id)
                    .options(selectinload(Project.vision))
                )).scalar_one_or_none()
                if project and project.vision and project.vision.content:
                    vision_context = (
                        f"\n\n## Project Vision\n{project.vision.content[:2000]}"
                    )

            # ── 4. Execute each workflow step ──
            step_context: dict = {
                "task_title": task.title,
                "task_description": task.description or "",
                "repository": repo_full_name,
                "branch": branch_name or "main",
                "vision": vision_context,
            }

            runner = HybridRunner(
                api_key=api_key,
                use_subscription=self.use_subscription,
                claude_cmd=self.claude_cmd,
            )

            all_succeeded = True

            for step in steps:
                agent: AgentDefinition = step.agent
                logger.info(f"  🐦 Step {step.order}: {step.name} ({agent.slug})")

                # Human approval gate
                if step.requires_approval:
                    task.status = TaskStatus.AWAITING_APPROVAL
                    await db.commit()
                    await self._publish_event(
                        task_id, EventType.APPROVAL_REQUEST,
                        f"Step '{step.name}' requires approval"
                    )
                    approved = await self._wait_for_approval(db, task_id, timeout=3600)
                    if not approved:
                        task.status = TaskStatus.REJECTED
                        await db.commit()
                        return
                    task.status = TaskStatus.IN_PROGRESS

                # Create execution record
                execution = Execution(
                    task_id=task_id,
                    agent_id=agent.id,
                    workflow_step_id=step.id,
                    agent_name=agent.name,
                    model_used=agent.model,
                    status=ExecutionStatus.RUNNING,
                    input_context=step_context,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(execution)
                await db.flush()

                # Build enriched brief with vision + prior step outputs
                brief = self._build_brief(step, step_context)

                # Publish start event
                await self._publish_event(
                    task_id, EventType.STATUS_CHANGE,
                    f"Agent '{agent.name}' started on step '{step.name}'",
                    execution_id=execution.id,
                )

                # Run the crow with the real workspace
                result = await runner.run(
                    system_prompt=agent.system_prompt + vision_context,
                    task_brief=brief,
                    model=agent.model,
                    tool_packs=agent.tool_packs,
                    workspace=str(workspace),
                    max_tokens=agent.max_tokens,
                    max_iterations=50,
                )

                # Record result
                execution.status = (
                    ExecutionStatus.COMPLETED if result.success
                    else ExecutionStatus.FAILED
                )
                execution.result_summary = result.content[:2000] if result.content else None
                execution.error_message = result.error
                execution.tokens_input = result.tokens_input
                execution.tokens_output = result.tokens_output
                execution.cost_usd = result.cost_usd
                execution.completed_at = datetime.now(timezone.utc)
                execution.duration_seconds = result.duration_seconds
                execution.output_context = {
                    "content": result.content[:5000]
                } if result.content else {}

                task.total_cost_usd += result.cost_usd
                task.total_tokens += result.tokens_input + result.tokens_output

                event = ExecutionEvent(
                    execution_id=execution.id,
                    event_type=EventType.OUTPUT if result.success else EventType.ERROR,
                    content=result.content[:5000] if result.content else result.error or "No output",
                )
                db.add(event)
                await db.commit()

                await self._publish_event(
                    task_id, EventType.STATUS_CHANGE,
                    f"Agent '{agent.name}' {'completed' if result.success else 'failed'} "
                    f"({result.duration_seconds:.1f}s, ${result.cost_usd:.4f}, "
                    f"{result.tool_calls} tool calls)",
                    execution_id=execution.id,
                )

                # Track for PR summary
                step_summaries.append({
                    "agent": agent.name,
                    "step": step.name,
                    "success": result.success,
                    "duration": result.duration_seconds,
                    "tool_calls": result.tool_calls,
                    "output_preview": result.content[:200] if result.content else "",
                })

                # Pass output to next step
                step_context[f"step_{step.name.lower()}_output"] = result.content

                # Handle failure
                if not result.success:
                    if step.on_fail == "skip":
                        logger.info(f"    ⏭️  Skipping failed step '{step.name}'")
                        continue
                    elif step.on_fail == "retry":
                        logger.info(f"    🔄 Retry not yet implemented, failing")
                        all_succeeded = False
                        task.status = TaskStatus.FAILED
                        await db.commit()
                        break
                    else:
                        all_succeeded = False
                        task.status = TaskStatus.FAILED
                        await db.commit()
                        break

            # ── 5. Commit, push, create PR ──
            pr_url = None
            if all_succeeded and branch_name and repo_full_name and github_token:
                try:
                    commit_msg = (
                        f"feat: {task.title}\n\n"
                        f"Automated by Cawnex (task #{task_id})"
                    )
                    if issue_number:
                        commit_msg += f"\n\nCloses #{issue_number}"

                    has_changes = commit_and_push(
                        workspace, branch_name, commit_msg,
                        github_token, repo_full_name,
                    )

                    if has_changes:
                        gh = GitHubAPI(github_token)
                        pr = await create_pull_request(
                            gh, repo_full_name, branch_name,
                            task.title,
                            task.description,
                            issue_number,
                            step_summaries,
                        )
                        pr_url = pr.get("html_url")

                        # Update task with PR info
                        task.context = {
                            **(task.context or {}),
                            "pr_number": pr["number"],
                            "pr_url": pr_url,
                        }

                        # Update issue
                        if issue_number:
                            await update_issue_status(
                                gh, repo_full_name, issue_number,
                                labels=["cawnex:pr-created"],
                                comment=f"🐦‍⬛ PR created: {pr_url}",
                            )

                        await gh.close()
                        logger.info(f"  🔀 PR: {pr_url}")
                    else:
                        logger.info("  📭 No file changes — skipping PR")

                except Exception as e:
                    logger.error(f"PR creation failed: {e}", exc_info=True)
                    # Don't fail the task just because PR creation failed
                    await self._publish_event(
                        task_id, EventType.ERROR,
                        f"PR creation failed: {e}",
                    )

            # ── 6. Final status ──
            if all_succeeded:
                task.status = TaskStatus.COMPLETED
            await db.commit()

            status_emoji = "✅" if all_succeeded else "❌"
            logger.info(
                f"{status_emoji} Task {task_id} {'completed' if all_succeeded else 'failed'} — "
                f"${task.total_cost_usd:.4f}, {task.total_tokens} tokens"
                f"{f', PR: {pr_url}' if pr_url else ''}"
            )

            # ── 7. Cleanup ──
            if workspace:
                cleanup_nest(workspace)

    def _decrypt_api_key(self, llm_config: LLMConfig | None) -> str | None:
        if not llm_config or not self.fernet_key:
            return None
        try:
            fernet = Fernet(self.fernet_key)
            return fernet.decrypt(llm_config.encrypted_api_key).decode()
        except Exception:
            return None

    def _build_brief(self, step: WorkflowStep, context: dict) -> str:
        """Build the task brief for a workflow step."""
        parts = [
            f"## Task: {context.get('task_title', 'Unknown')}",
            "",
            context.get("task_description", ""),
            "",
        ]

        if context.get("repository"):
            parts.append(f"Repository: {context['repository']}")
            parts.append("")

        # Include output from previous steps
        for key, value in context.items():
            if key.startswith("step_") and key.endswith("_output"):
                step_name = key.replace("step_", "").replace("_output", "")
                parts.append(f"### Output from {step_name} step:")
                parts.append(value[:3000])
                parts.append("")

        return "\n".join(parts)

    async def _publish_event(
        self, task_id: int, event_type: str, content: str, execution_id: int | None = None
    ) -> None:
        """Publish event to Redis Stream for SSE consumers."""
        await self.redis.xadd(
            f"cawnex:events:{task_id}",
            {
                "type": event_type,
                "content": content,
                "execution_id": str(execution_id) if execution_id else "",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _wait_for_approval(self, db: AsyncSession, task_id: int, timeout: int = 3600) -> bool:
        """Poll DB for task approval. Returns True if approved."""
        import time
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            await asyncio.sleep(5)
            result = await db.execute(select(Task.status).where(Task.id == task_id))
            db.expire_all()
            status = result.scalar()
            if status == TaskStatus.APPROVED:
                return True
            if status == TaskStatus.REJECTED:
                return False
        return False


async def main():
    """Entry point for the worker process."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    murder = Murder(
        database_url=os.environ.get("CAWNEX_DATABASE_URL", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex"),
        redis_url=os.environ.get("CAWNEX_REDIS_URL", "redis://localhost:6380"),
        fernet_key=os.environ.get("CAWNEX_FERNET_KEY", ""),
        github_token=os.environ.get("CAWNEX_GITHUB_TOKEN"),
        use_subscription=os.environ.get("CAWNEX_USE_SUBSCRIPTION", "").lower() in ("1", "true", "yes"),
        claude_cmd=os.environ.get("CAWNEX_CLAUDE_CMD"),
    )

    try:
        await murder.start()
    except KeyboardInterrupt:
        pass
    finally:
        await murder.stop()


if __name__ == "__main__":
    asyncio.run(main())
