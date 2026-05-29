# Prompt Packet Template

Use this when preparing a model panel request.

```markdown
# Goal
One short paragraph on what decision, answer, or comparison you need.

# Current State
- Fact 1
- Fact 2
- Fact 3

# Constraints
- Constraint 1
- Constraint 2
- Constraint 3

# Questions
1. Question one
2. Question two
3. Question three

# Output Contract
Return plain text.
Lead with findings, not preamble.
Call out uncertainty when evidence is weak.
Do not use Markdown tables unless asked.
```

## Notes

- Keep `Current State` factual.
- Prefer numbered questions.
- Ask for concrete output structure when you plan to compare several answers.
- If the task is code-heavy, include exact file paths or snippets.
- If the task is image-grounded, say what the image is supposed to prove or clarify.

