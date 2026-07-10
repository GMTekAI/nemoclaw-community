# NV Tech Assistant

This example turns your NemoClaw agent into a grounded NVIDIA technical assistant. The `nv-tech-assistant` skill answers NVIDIA technical questions — "how do I use this SDK", "recommend an NVIDIA model for X", "how do I fix this TensorRT error" — by searching authorized NVIDIA sources (docs.nvidia.com, developer.nvidia.com, the NGC catalog, build.nvidia.com, the developer blog and forums, NVIDIA's GitHub orgs, the nvidia Hugging Face org, and arXiv) and citing real, verbatim-quoted evidence instead of answering from memory.

Beyond the skill itself, this example is a minimal, reusable recipe for two common customizations:

1. **Adding a custom skill** to a running sandbox — upload a folder, no rebuild.
2. **Adding custom network policies** so the agent can reach the sites a skill needs — applied at runtime with a YAML file, no rebuild.

Both steps generalize directly to your own skills and policies.

## Layout

```
nv-tech-assistant/
├── policies/                      # network policies the skill needs
│   ├── arxiv.yaml                 #   arxiv.org, export.arxiv.org
│   ├── github_ext.yaml            #   github.com, api.github.com, raw.githubusercontent.com
│   └── nvidia_ext.yaml            #   *.nvidia.com sites (docs, developer, build, NGC, ...)
└── skills/
    └── nv-tech-assistant/
        ├── SKILL.md               # the skill: principles, workflow, question-type playbooks
        └── references/
            ├── nvidia-landscape.md            # product disambiguation map
            ├── sources-and-search.md          # search recipes and URL patterns per source
            ├── nemoclaw-network-policy.md     # how the agent helps you author new policies
            └── nemoclaw-policy-template.yaml  # annotated policy template
```

## Prerequisites

- A NemoClaw installation with an onboarded, running sandbox. If you haven't onboarded yet, follow the [NemoClaw](https://github.com/NVIDIA/NemoClaw) getting-started guide first.
- **Recommended (optional):** enable Brave Web Search during onboarding and provide a [Brave Search API key](https://brave.com/search/api/). The skill prefers the `WebSearch` tool for scoped queries (`site:docs.nvidia.com`, ...) and falls back to the sources' structured search endpoints when it is unavailable — so the skill works without it, just better with it.

## Step 1 — Add the network policies

The skill needs outbound access to the NVIDIA sites, GitHub, and arXiv. The `./policies` directory contains the three policy files that open exactly those endpoints. Apply them from this directory on the host — the policies take effect immediately on the running sandbox, no rebuild needed:

```bash
# apply the whole directory
nemoclaw <sbx-name> policy-add --from-dir ./policies/ --yes
```

Verify with:

```bash
nemoclaw <sbx-name> policy-list
```

To write your own custom policy, use the YAML files in `./policies` as a reference, save it as `<domain-name>.yaml`, and apply it with `nemoclaw <sbx-name> policy-add --from-file <domain-name>.yaml`.

## Step 2 — Add the skill

Upload the skill folder directly to the sandbox — it is recognized by OpenClaw at runtime:

```bash
nemoclaw <sbx-name> upload skills/nv-tech-assistant /sandbox/.openclaw/skills/
```

The same command works for any custom skill: a folder with a `SKILL.md` (plus optional `references/`) uploaded to `/sandbox/.openclaw/skills/`.

## Step 3 — Try it

Talk to the agent through the OpenClaw TUI:

```bash
nemoclaw <sbx-name> connect
openclaw tui
```

or through any messaging channel you connected during onboarding. Example prompts (invoking `/nv_tech_assistant` at the start guarantees the skill is used):

- *"/nv_tech_assistant how can I get access to medium.com in the sandbox"*
- *"/nv_tech_assistant recommend an NVIDIA model for speech recognition."*
- *"/nv_tech_assistant I'm getting `CUDA error: out of memory` with Triton Inference Server — how do I fix it?"*
- *"/nv_tech_assistant show me a real customer success story for NVIDIA Riva."*

Answers come back with inline citations to the exact pages the agent retrieved, and any code is quoted verbatim from official sources with a link.

## Bonus: the skill can author policies too

The skill knows it runs inside a sandbox with restricted egress. When you want to open access to a new site — or the agent hits a source the network policy blocks — just ask it, for example:

- *"/nv_tech_assistant how can I get access to medium.com in the sandbox"*

The agent drafts the policy YAML for the host(s) and hands you the exact `nemoclaw <sbx-name> policy-add --from-file <domain-name>.yaml` command to run on your host machine (it cannot change the policy from inside the sandbox).
