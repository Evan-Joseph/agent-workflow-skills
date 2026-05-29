---
name: multi-model-consultation
description: "Consult multiple external models on the same task and compare their answers. Use when the user wants outside opinions, when a decision benefits from model diversity, or when one model's answer should be checked against a small panel before acting."
metadata:
  short-description: "Compare several external model opinions"
  category: "model-routing"
  version: "1.0.0"
---

# Multi-Model Consultation

Use this skill when one model answer is not enough.

The agent stays in charge. External models are treated as advisors, not authorities. The point is to collect different answers, compare them, and then make one clear recommendation.

## Good use cases

- the user explicitly asks for outside model opinions
- a high-cost decision would benefit from cross-checking
- you want a second look at a design, plan, or technical tradeoff
- one answer looks plausible but still feels under-verified
- you want to compare writing, coding, reasoning, or vision outputs from different models

Do not use it for simple facts that can be verified directly from source material.

## Workflow

### 1. Build a consultation packet

For non-trivial tasks, write a short prompt file with:

- **Goal**: what you need from the panel
- **Current state**: confirmed facts only
- **Constraints**: cost, safety, product, style, time, or implementation limits
- **Questions**: numbered, concrete questions
- **Output contract**: how the models should answer

Keep the packet clean. Leave out sunk cost, favorite options, and emotional framing unless they change the decision boundary.

### 2. Choose the panel

Use the smallest panel that answers the question.

Common patterns:

- **analysis**: planning, tradeoffs, synthesis
- **coding**: implementation, debugging, review
- **writing**: copy, tone, structure
- **vision**: screenshots, layouts, images
- **premium**: only when the user asks for top-tier arbitration or lower-cost models leave important uncertainty

Do not start with the most expensive panel by habit.

### 3. Run the models

The exact script, provider, and model roster depend on the local environment. The public workflow is:

```bash
python3 "$MODEL_PANEL_SCRIPT" --list-models

python3 "$MODEL_PANEL_SCRIPT" \
  --models analysis \
  --prompt-file /tmp/model-panel.md
```

For image-grounded tasks:

```bash
python3 "$MODEL_PANEL_SCRIPT" \
  --models vision \
  --prompt-file /tmp/model-panel.md \
  --image /absolute/path/to/input.png
```

If the local tool supports durable output, save raw responses:

```bash
python3 "$MODEL_PANEL_SCRIPT" \
  --models analysis \
  --prompt-file /tmp/model-panel.md \
  --json-output /tmp/model-panel.json
```

### 4. Compare the answers

Do not just average them. Look for:

- consensus
- real disagreement
- unsupported confidence
- missing constraints
- better framing of the same problem
- one model catching something the others ignored

Quote or summarize only the parts that change the decision.

### 5. Make the final call

Your final answer should include:

- the main conclusion
- where the panel agreed
- where the panel disagreed
- your own judgment
- the next action

If one model is clearly best for the next step, say so and explain why.

## Boundaries

- Do not send secrets, live credentials, session data, or private keys to external models.
- Do not send raw proprietary documents unless the user has approved that exposure.
- Do not treat model majority vote as proof.
- Do not escalate to expensive models without a reason.
- Do not let a panel replace direct source verification when primary evidence is available.

## Local adaptation

This public skill is provider-neutral on purpose. Local installations may define:

- a preferred provider
- environment variable names for credentials
- model groups such as `analysis`, `coding`, `vision`, or `premium`
- scripts for JSON output, retries, or arbitration

Keep those details in local references or scripts, not in the public skill body.
