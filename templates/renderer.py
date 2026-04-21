"""Render CORTEX.md from retrieved constraints."""

from __future__ import annotations

from datetime import datetime

from agents.retriever import RetrievedConstraint


def render_cortex_markdown(
    repo_name: str,
    branch_name: str,
    constraints: list[RetrievedConstraint],
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []
    for constraint in constraints:
        sections.append(
            "\n".join(
                [
                    f"**[{constraint.constraint_id}]** {constraint.title}",
                    f"NEVER: {constraint.never_do}",
                    f"BECAUSE: {constraint.because}",
                    f"INSTEAD: {constraint.instead}",
                ]
            )
        )
    body = "\n\n".join(sections) if sections else "No active constraints retrieved."
    return (
        "# CORTEX - Active Constraints for This Session\n\n"
        f"Generated: {generated_at} | Repo: {repo_name} | Branch: {branch_name}\n\n"
        "## Before you start - read these constraints\n\n"
        f"{body}\n"
    )
