# Incremento: Reviewer Context Optimization

## 🎯 Objetivo

Reduzir contexto do reviewer de 183 arquivos → git diff + arquivos modificados apenas.
**Impacto esperado:** $0.11/step → $0.01/step (90% redução de custo)

## 🔧 Implementação

### 1. Nova função de contexto para reviewer

````python
def gather_reviewer_context(worktree_dir: str, base_branch: str = "main") -> str:
    """Context otimizado para reviewer: apenas diff + arquivos modificados."""
    context_parts = []

    # 1. Git diff summary
    diff_summary = run_git(f"git diff --stat {base_branch}..HEAD", cwd=worktree_dir)
    context_parts.append(f"## Changes Summary\n```\n{diff_summary}\n```\n")

    # 2. Full diff content
    diff_content = run_git(f"git diff {base_branch}..HEAD", cwd=worktree_dir)
    context_parts.append(f"## Git Diff\n```diff\n{diff_content}\n```\n")

    # 3. Modified files context (apenas arquivos alterados)
    modified_files = run_git(f"git diff --name-only {base_branch}..HEAD", cwd=worktree_dir).split('\n')
    modified_files = [f.strip() for f in modified_files if f.strip()]

    context_parts.append(f"## Modified Files ({len(modified_files)} files)")

    for filepath in modified_files[:10]:  # Max 10 arquivos modificados
        fullpath = os.path.join(worktree_dir, filepath)
        if os.path.exists(fullpath):
            try:
                with open(fullpath, "r", errors="ignore") as f:
                    content = f.read()
                context_parts.append(f"### {filepath}\n```\n{content}\n```\n")
            except Exception as e:
                context_parts.append(f"### {filepath}\n*Could not read: {e}*\n")

    return "\n\n".join(context_parts)
````

### 2. Modificar chamada para reviewer

```python
# linha ~500 em handler.py - na função que chama o crow
if crow == "reviewer":
    context = gather_reviewer_context(worktree_dir, base_branch="main")
else:
    context = gather_code_context(worktree_dir, max_files=30)
```

### 3. Atualizar prompt do reviewer

```python
"reviewer": """You are a reviewer crow. Review the git diff and code changes.

You will receive:
- Changes summary (files modified, lines added/removed)
- Full git diff showing exact changes
- Content of modified files for context

Focus on:
- Code quality and best practices
- Potential bugs or issues
- Performance implications
- Security concerns

Output JSON:
{
  "approved": true | false,
  "issues": ["Issue 1", "Issue 2"],
  "suggestions": ["Suggestion 1"],
  "summary": "Review summary focusing on the actual changes"
}""",
```

## 📊 Resultado Esperado

**Contexto Atual:**

- 183 arquivos no worktree
- 30 arquivos lidos completos (~50KB cada)
- ~1.5MB de contexto = $0.11/step

**Contexto Otimizado:**

- Git diff (~5-20KB)
- 3-5 arquivos modificados (~150KB total)
- ~200KB de contexto = $0.01/step

**Redução:** 90% nos custos + reviewer foca apenas nas mudanças relevantes.

## ✅ Validação

- Testar com issue #4 existente
- Comparar qualidade das reviews
- Medir redução de custos
- Verificar se mantém same quality standards
