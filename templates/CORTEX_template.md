# CORTEX - Active Constraints for This Session

Generated: {{ generated_at }} | Repo: {{ repo_name }} | Branch: {{ branch_name }}

## Before you start - read these constraints

{{ constraints }}

## When the user corrects you

If the user pushes back on something you did — tells you it's wrong, asks you to redo it, or overrides your approach — call the `cortex_flag` MCP tool before moving on. Pass:
- `code_context`: the code or approach you proposed
- `error_context`: what the user said was wrong
- `learned_rule`: the rule to follow next time
