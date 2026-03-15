"""Section definitions and AI prompts for all document types.

Each document type has a list of sections with:
- id: unique within the document
- title: section heading
- question: what the AI asks the founder
- description: context for Claude about what this section should capture

Sections are ordered — the AI asks them in sequence.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class SectionDefinition:
    """Definition of a document section."""

    id: str
    title: str
    question: str
    description: str


# ============================================================
# VISION — Product strategy and direction
# Based on YC application, lean canvas, and startup best practices
# ============================================================

VISION_SECTIONS: List[SectionDefinition] = [
    SectionDefinition(
        id="s1",
        title="Problem Statement",
        question=(
            "What's the core problem you're solving? "
            "Describe the pain — who feels it, how often, "
            "and what they do today instead."
        ),
        description=(
            "A clear statement of the problem: who has it, "
            "how painful it is, and why existing solutions fail."
        ),
    ),
    SectionDefinition(
        id="s2",
        title="Target User",
        question=(
            "Who is your primary user? Describe them in terms of "
            "their role, experience level, and the specific context "
            "where they'll use your product."
        ),
        description=(
            "A specific user profile: role, stage, context. "
            "Not a market segment — a person you can picture."
        ),
    ),
    SectionDefinition(
        id="s3",
        title="Core Value Proposition",
        question=(
            "What's the single most important outcome your product delivers? "
            "Not features — the transformation. What becomes true for "
            "the user after using it?"
        ),
        description=(
            "One sentence: For [user], [product] delivers [outcome] "
            "by eliminating [friction]."
        ),
    ),
    SectionDefinition(
        id="s4",
        title="Key Differentiators",
        question=(
            "What makes your approach fundamentally different from "
            "existing solutions? What would a competitor need to "
            "copy to match you?"
        ),
        description=(
            "3-4 concrete differentiators. Not adjectives like "
            "'faster' — structural advantages or unique approaches."
        ),
    ),
    SectionDefinition(
        id="s5",
        title="Success Metrics",
        question=(
            "How will you know if this is working in 6 months? "
            "Name 2-3 specific, measurable outcomes — not activity "
            "metrics like signups, but value metrics."
        ),
        description=(
            "Numbered list: metric + target value + timeframe. "
            "Focus on outcomes, not vanity metrics."
        ),
    ),
    SectionDefinition(
        id="s6",
        title="Non-Goals",
        question=(
            "What are you explicitly NOT building in the first version? "
            "What decisions have you already made to keep scope tight?"
        ),
        description=(
            "Bulleted list of what's out of scope and why. "
            "Shows discipline and focus."
        ),
    ),
]

# ============================================================
# ARCHITECTURE — Technical system design
# Based on C4 model, AWS well-architected, and 12-factor app
# ============================================================

ARCHITECTURE_SECTIONS: List[SectionDefinition] = [
    SectionDefinition(
        id="a1",
        title="System Overview",
        question=(
            "Describe your system in one paragraph. What does it do, "
            "who uses it, and what are the main moving parts at the "
            "highest level?"
        ),
        description=(
            "One paragraph: what the system does, who interacts with it, "
            "and the 3-5 major components."
        ),
    ),
    SectionDefinition(
        id="a2",
        title="High-Level Components",
        question=(
            "What are the main components of your system and how do "
            "they interact? Think: frontend, backend, database, "
            "external services, queues, workers."
        ),
        description=(
            "Component list with brief description of each. "
            "How they communicate (HTTP, events, queues)."
        ),
    ),
    SectionDefinition(
        id="a3",
        title="Data Flow",
        question=(
            "Walk me through a typical user request from the moment "
            "they tap a button to the final response. What systems "
            "does it touch in order?"
        ),
        description=(
            "Step-by-step flow of a primary use case through the system. "
            "Shows how components connect in practice."
        ),
    ),
    SectionDefinition(
        id="a4",
        title="Data Model",
        question=(
            "What are the core entities in your data model? "
            "What database(s) will you use and why? "
            "Any key patterns like single-table, event sourcing, CQRS?"
        ),
        description=(
            "Core entities, relationships, storage choices, "
            "and data access patterns."
        ),
    ),
    SectionDefinition(
        id="a5",
        title="Security Model",
        question=(
            "How do you handle authentication, authorization, and "
            "data isolation? What's your approach to secrets, "
            "encryption, and tenant boundaries?"
        ),
        description=(
            "Auth mechanism, tenant isolation strategy, "
            "encryption at rest/transit, secrets management."
        ),
    ),
    SectionDefinition(
        id="a6",
        title="Infrastructure & Deployment",
        question=(
            "Where does this run? Cloud provider, compute model "
            "(serverless, containers, VMs), CI/CD approach, "
            "and how you handle environments (dev/staging/prod)."
        ),
        description=(
            "Cloud provider, compute model, IaC approach, "
            "CI/CD pipeline, environment strategy."
        ),
    ),
    SectionDefinition(
        id="a7",
        title="Technology Decisions",
        question=(
            "What are the key technology choices you've made and why? "
            "Language, framework, database, and any tools you've "
            "specifically chosen or rejected."
        ),
        description=(
            "Key tech choices with rationale. "
            "What was considered and why it was chosen or rejected."
        ),
    ),
]

# ============================================================
# GLOSSARY — Shared vocabulary
# Based on domain-driven design ubiquitous language
# ============================================================

GLOSSARY_SECTIONS: List[SectionDefinition] = [
    SectionDefinition(
        id="g1",
        title="Domain Terms",
        question=(
            "What are the core domain-specific terms your team uses "
            "that might be unfamiliar to new contributors? "
            "List them with brief definitions."
        ),
        description=(
            "Domain-specific vocabulary: terms that have special "
            "meaning in this project's context."
        ),
    ),
    SectionDefinition(
        id="g2",
        title="User-Facing Terms",
        question=(
            "What terms do your end users see in the app? "
            "Things like project, task, credit — the vocabulary "
            "of the product interface."
        ),
        description=(
            "Terms visible to users in the UI. "
            "Consistent naming across screens and documentation."
        ),
    ),
    SectionDefinition(
        id="g3",
        title="Technical Terms",
        question=(
            "What technical terms does your team use that aren't "
            "standard industry terms? Internal names for services, "
            "patterns, or abstractions you've created."
        ),
        description=(
            "Internal technical vocabulary: service names, "
            "architectural patterns, custom abstractions."
        ),
    ),
    SectionDefinition(
        id="g4",
        title="Business Terms",
        question=(
            "What business concepts are important to your product? "
            "Pricing models, user segments, lifecycle stages, "
            "or metrics you track."
        ),
        description=(
            "Business vocabulary: pricing concepts, user segments, "
            "lifecycle stages, KPIs."
        ),
    ),
    SectionDefinition(
        id="g5",
        title="Abbreviations & Acronyms",
        question=(
            "What abbreviations or acronyms does your team use? "
            "List them with their full form and brief context."
        ),
        description=(
            "Abbreviations and acronyms used in code, docs, "
            "or conversation. Full form + context."
        ),
    ),
]

# ============================================================
# DESIGN SYSTEM — Visual identity and component library
# Based on Material Design, Apple HIG, and design token standards
# ============================================================

DESIGN_SECTIONS: List[SectionDefinition] = [
    SectionDefinition(
        id="d1",
        title="Visual Identity",
        question=(
            "What's the visual identity you're going for? "
            "Describe the mood, aesthetic, and any brand colors "
            "or inspirations you have in mind."
        ),
        description=(
            "Brand aesthetic: mood, color palette, "
            "visual references, light/dark mode preference."
        ),
    ),
    SectionDefinition(
        id="d2",
        title="Typography",
        question=(
            "What font families will you use? Do you have a "
            "type scale in mind — heading sizes, body text, "
            "captions? Any specific font choices?"
        ),
        description=(
            "Font families, type scale (heading/body/caption sizes), "
            "weight usage, monospace for code."
        ),
    ),
    SectionDefinition(
        id="d3",
        title="Spacing & Layout",
        question=(
            "What spacing system will you use? A fixed scale "
            "like 4/8/12/16/24? How about corner radius, "
            "card padding, and screen margins?"
        ),
        description=(
            "Spacing scale, corner radius tokens, "
            "card padding, screen margins, grid system."
        ),
    ),
    SectionDefinition(
        id="d4",
        title="Component Patterns",
        question=(
            "What are the key reusable components in your UI? "
            "Cards, buttons, status chips, progress bars, "
            "input fields — describe the patterns you use."
        ),
        description=(
            "Core UI components: cards, buttons, inputs, "
            "status indicators, navigation patterns."
        ),
    ),
    SectionDefinition(
        id="d5",
        title="Iconography",
        question=(
            "What icon set will you use? SF Symbols, Lucide, "
            "custom icons? Any specific icon conventions — "
            "filled vs outlined, sizes?"
        ),
        description=(
            "Icon library, style conventions (filled/outlined), "
            "standard sizes, custom icon guidelines."
        ),
    ),
    SectionDefinition(
        id="d6",
        title="Motion & Interaction",
        question=(
            "How should things move in your app? Transition "
            "styles, animation durations, loading states, "
            "haptic feedback — what's the feel?"
        ),
        description=(
            "Animation principles: transition types, durations, "
            "easing curves, loading patterns, haptics."
        ),
    ),
]

# ============================================================
# Registry — look up sections by document type
# ============================================================

DOCUMENT_SECTIONS: Dict[str, List[SectionDefinition]] = {
    "vision": VISION_SECTIONS,
    "architecture": ARCHITECTURE_SECTIONS,
    "glossary": GLOSSARY_SECTIONS,
    "design": DESIGN_SECTIONS,
}


def get_sections(doc_type: str) -> List[SectionDefinition]:
    """Get section definitions for a document type."""
    sections = DOCUMENT_SECTIONS.get(doc_type)
    if sections is None:
        raise ValueError(f"Unknown document type: {doc_type}")
    return sections
