# Murder/Crow System: Optimization Strategies

## Strategic Prompt Design for Auto-Caching

### Core Principle: Strategic Redundancy

Claude SDK automatically caches repeated content within prompts. We exploit this by intentionally repeating critical context throughout prompts.

### Repetition Patterns

**High-Value Repetitions (3-4x per prompt):**

```markdown
1. Project quality standards
2. Coding patterns & conventions
3. Security requirements
4. Performance criteria
```

**Medium-Value Repetitions (2-3x per prompt):**

```markdown
1. Memory learnings summary
2. Architectural principles
3. Error handling patterns
4. Testing requirements
```

### Example Optimized Prompt Structure

```python
def build_strategic_prompt(crow_type, task, memory):
    return f"""
    # CONTEXT: {crow_type} Crow Assignment

    ## Project Standards (CRITICAL)
    {project_standards}

    ## Your Role: Expert {crow_type}
    {crow_specific_instructions}

    ## Task Details
    {task.description}

    ## Quality Requirements
    Remember these standards: {project_standards}  # CACHED REPEAT

    ## Previous Learnings
    {memory.recent_patterns}

    ## Implementation Guidelines
    Follow established patterns: {project_standards}  # CACHED REPEAT
    Apply these learnings: {memory.recent_patterns}   # CACHED REPEAT

    ## Final Checklist
    □ Meets project standards: {project_standards}    # CACHED REPEAT
    □ Incorporates learnings: {memory.recent_patterns} # CACHED REPEAT
    □ Follows {crow_type} best practices

    Execute with full adherence to: {project_standards} # CACHED REPEAT
    """
```

## Memory System Architecture

### File-Based Learning Structure

```
memory/
├── crows/
│   ├── planner/
│   │   ├── planner-001-summary.md       # Individual crow memory
│   │   ├── planner-patterns.md          # Cross-planner learnings
│   │   └── planner-failures.md          # Anti-patterns to avoid
│   ├── implementer/
│   │   ├── implementer-042-summary.md
│   │   ├── code-patterns.md
│   │   └── quality-issues.md
│   ├── reviewer/
│   │   ├── reviewer-017-summary.md
│   │   ├── review-criteria.md
│   │   └── common-oversights.md
│   └── fixer/
│       ├── fixer-023-summary.md
│       ├── bug-patterns.md
│       └── solution-strategies.md
├── project/
│   ├── architecture-learnings.md        # Project-specific insights
│   ├── team-preferences.md              # Human feedback patterns
│   └── integration-challenges.md        # Cross-system complexities
└── cross-cutting/
    ├── performance-optimizations.md     # Speed/efficiency learnings
    ├── security-patterns.md             # Security implementation wisdom
    └── deployment-strategies.md         # DevOps automation learnings
```

### Memory Content Templates

**Individual Crow Memory:**

```markdown
# Implementer Crow #042 - Learning Summary

## Execution History

- Waves completed: 15
- Success rate: 73% first attempt
- Average retry count: 1.4

## Successful Patterns

### Code Organization

- Always create `types/` directory for shared types
- Use `utils/` for pure functions, `services/` for business logic
- Keep components under 200 lines for maintainability

### Testing Approaches

- Write tests before implementation (TDD)
- Mock external dependencies consistently
- Aim for 85%+ coverage to exceed project 80% requirement

### Quality Gates

- Run `npm run ci:quick` before every commit
- Use project's error handling patterns from `src/errors/`
- Follow TypeScript strict mode without `any` types

## Failed Approaches & Lessons

### What Doesn't Work

- Large monolithic components (>300 lines) → Split into smaller pieces
- Cross-context imports → Respect bounded context boundaries
- Skipping test setup → Always causes delays later

### Recovery Strategies

- When tests fail: Check for missing dependencies (httpx, etc.)
- When linting fails: Run formatters before submission
- When builds fail: Verify all imports and types

## Project-Specific Insights

### Cawnex Patterns

- Use existing authentication patterns in `contexts/auth/`
- Follow error handling from `src/errors/ErrorBoundary.tsx`
- iOS config updates need special handling via scripts

### Team Preferences

- Prefer smaller, focused PRs over large changes
- Include documentation updates with feature changes
- Use descriptive commit messages following conventional commits

## Performance Metrics

- Average tokens per execution: 38k
- Average completion time: 18 minutes
- Memory application success rate: 89%
```

**Cross-Crow Pattern Library:**

```markdown
# Successful Interaction Patterns

## Planner → Implementer Handoffs

### What Works

- Clear acceptance criteria with concrete examples
- Specific file/directory structure recommendations
- Test case definitions included in planning
- Dependencies and integration points identified

### What Fails

- Vague requirements without examples
- Missing dependency analysis
- Unclear success criteria

## Implementer → Reviewer Workflows

### Effective Reviews

- Focus on project-specific patterns compliance
- Check test coverage and quality
- Validate error handling consistency
- Confirm documentation completeness

### Review Failure Patterns

- Nitpicking style over substance
- Missing architectural concerns
- Ignoring performance implications

## Cross-Wave Learning Transfer

### Pattern Recognition

- Similar MVIs in different waves
- Reusable components and utilities
- Common integration challenges
- Deployment automation patterns
```

## Cost Optimization Tactics

### Token Efficiency Strategies

**1. Context Compression:**

```python
def compress_context(full_context):
    """Reduce context size while maintaining essential information."""
    return {
        'architecture': summarize_to_bullets(full_context.architecture),
        'patterns': extract_key_patterns(full_context.patterns),
        'constraints': list_critical_constraints(full_context.constraints),
        'examples': select_best_examples(full_context.examples, max_count=3)
    }
```

**2. Progressive Context Loading:**

```python
def build_progressive_prompt(crow_type, task_complexity):
    """Load context based on task complexity."""
    base_context = get_essential_context()

    if task_complexity == 'simple':
        return base_context
    elif task_complexity == 'moderate':
        return base_context + get_detailed_patterns()
    else:  # complex
        return base_context + get_detailed_patterns() + get_edge_cases()
```

**3. Smart Retry Logic:**

```python
def intelligent_retry(crow, failure_reason, attempt_count):
    """Adjust prompt based on failure type."""
    if failure_reason == 'quality_standards':
        return enhance_quality_emphasis(crow.prompt)
    elif failure_reason == 'integration_issues':
        return add_integration_context(crow.prompt)
    elif failure_reason == 'test_failures':
        return emphasize_testing_patterns(crow.prompt)
    else:
        return add_debugging_context(crow.prompt)
```

### Parallel Execution Optimization

**Wave Parallelization Strategy:**

```python
class WaveExecutor:
    def __init__(self, max_parallel_waves=4):
        self.max_parallel = max_parallel_waves
        self.dependency_graph = {}

    def execute_waves(self, waves):
        """Execute waves in parallel where dependencies allow."""
        ready_waves = self.get_ready_waves(waves)

        while ready_waves or self.has_running_waves():
            # Start new waves up to parallel limit
            for wave in ready_waves[:self.available_slots()]:
                self.start_wave_async(wave)

            # Check for completed waves and update dependencies
            completed = self.wait_for_completion()
            self.update_dependency_graph(completed)
            ready_waves = self.get_ready_waves(waves)
```

**Crow Parallelization within Waves:**

```python
async def execute_wave_crows(wave_mvids):
    """Execute implementer and reviewer crows in parallel."""
    implementer_tasks = [
        execute_implementer(mvi) for mvi in wave_mvids
    ]

    # Wait for all implementations
    implementations = await asyncio.gather(*implementer_tasks)

    # Start reviews in parallel
    review_tasks = [
        execute_reviewer(impl) for impl in implementations
    ]

    return await asyncio.gather(*review_tasks)
```

## Quality Assurance Integration

### Automated Quality Gates

**Pre-Execution Validation:**

```python
def validate_crow_readiness(crow, task):
    """Ensure crow has necessary context before execution."""
    validations = [
        has_sufficient_memory(crow),
        has_clear_acceptance_criteria(task),
        budget_within_limits(task.estimated_cost),
        dependencies_resolved(task.dependencies)
    ]

    if not all(validations):
        raise CrowNotReadyError(get_validation_failures(validations))
```

**Post-Execution Quality Checks:**

```python
def validate_crow_output(crow_output, quality_standards):
    """Automated quality validation before human review."""
    checks = [
        code_compiles(crow_output.code),
        tests_pass(crow_output.tests),
        coverage_adequate(crow_output.coverage),
        security_scan_clean(crow_output.code),
        documentation_complete(crow_output.docs)
    ]

    if not all(checks):
        return QualityFailure(get_failed_checks(checks))

    return QualityPass()
```

### Performance Monitoring

**Crow Performance Metrics:**

```python
class CrowMetrics:
    def __init__(self):
        self.success_rates = {}      # By crow type and task type
        self.token_efficiency = {}   # Tokens per deliverable
        self.time_efficiency = {}    # Minutes per completion
        self.learning_curves = {}    # Improvement over time

    def track_execution(self, crow, task, result):
        """Record performance data for optimization."""
        self.success_rates[crow.type][task.type] = result.success
        self.token_efficiency[crow.id] = result.tokens / result.output_quality
        self.time_efficiency[crow.id] = result.duration / result.deliverables

        if result.success:
            self.update_learning_curve(crow, task, result)
```

## Future Optimization Roadmap

### Short-term (1-3 months)

- **Memory system implementation** with file-based learning
- **Strategic redundancy** in all crow prompts
- **Parallel execution** for independent MVIs
- **Automated quality gates** integration

### Medium-term (3-6 months)

- **Cross-project learning** transfer between codebases
- **Predictive cost modeling** based on task complexity
- **Dynamic prompt optimization** based on success patterns
- **Advanced retry strategies** with failure analysis

### Long-term (6-12 months)

- **Hybrid local/cloud** execution for cost optimization
- **Domain-specific crow specialization** (fintech, healthcare, etc.)
- **Collaborative learning networks** across crow types
- **Real-time performance adaptation** based on current metrics

---

_These optimization strategies are designed to maximize both cost efficiency and output quality while maintaining system reliability and predictability._
