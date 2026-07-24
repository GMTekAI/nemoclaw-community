# NV Tech Assistant

NV Tech Assistant is a NemoClaw community example for grounded NVIDIA
technical research. It searches authorized NVIDIA sources, GitHub, and arXiv,
then answers with citations to evidence retrieved during the current task
instead of relying on model memory.

Use it for questions such as:

- How do I use an NVIDIA SDK or find an official sample?
- Which NVIDIA model, NIM, or library fits my use case?
- How do I troubleshoot an NVIDIA SDK error?
- Where is a documented NVIDIA customer success story?

## Quickstart

```bash
git clone https://github.com/NVIDIA/nemoclaw-community.git
cd nemoclaw-community/examples/nv-tech-assistant

cp .env.example .env      # add NVIDIA_INFERENCE_API_KEY; Brave is optional
bash scripts/onboard.sh   # create/configure the sandbox
bash scripts/install.sh   # apply policies and install the skill
bash scripts/start.sh     # ensure the sandbox is running
```

Ask a question non-interactively:

```bash
nemoclaw nv-tech-assistant agent --agent main -m \
  "/nv_tech_assistant recommend an NVIDIA model for speech recognition"
```

Or connect to the sandbox and launch the OpenClaw TUI:

```bash
nemoclaw nv-tech-assistant connect
openclaw tui
```

## Requirements

- Docker and [NemoClaw](https://github.com/NVIDIA/NemoClaw) installed.
- An NVIDIA Endpoints API key from <https://build.nvidia.com>.
- Optional: a Brave Search API key from <https://brave.com/search/api/>.

NVIDIA Endpoints is the default inference provider. When `BRAVE_API_KEY` is
set, onboarding enables Brave Search. When it is blank, web search is disabled
and the skill uses direct retrieval and structured search endpoints from its
allowlisted sources. See [`.env.example`](.env.example) for the exact
variables.

## Commands

Create the sandbox using `.env`:

```bash
bash scripts/onboard.sh
```

Apply the network policies and install or refresh the skill:

```bash
bash scripts/install.sh
```

Start or recover the sandbox:

```bash
bash scripts/start.sh
```

Stop the sandbox while preserving its workspace and credentials:

```bash
bash scripts/stop.sh
```

Restart it later with `scripts/start.sh`. To permanently delete the sandbox
instead, run `nemoclaw nv-tech-assistant destroy` and confirm the destructive
operation.

Override the default sandbox name in `.env`:

```env
NEMOCLAW_SANDBOX_NAME=my-nv-tech-assistant
```

Use that name in direct `nemoclaw` commands as well.

## How installation works

`scripts/install.sh` performs two host-side operations:

1. Applies every policy in `policies/` with `policy-add --from-dir`.
2. Deploys `skills/nv-tech-assistant/` with `skill install`.

Both operations target the sandbox named by `NEMOCLAW_SANDBOX_NAME`. Re-run
the script after editing a policy, the skill, or one of its references.

## Network policy

The assistant receives read-only REST access to the sources it researches:

- NVIDIA documentation, developer resources, blogs, forums, NGC, and
  build.nvidia.com
- NVIDIA repositories and files on GitHub
- arXiv pages and its metadata export endpoint

Every endpoint uses `access: read-only`, `protocol: rest`, and
`enforcement: enforce`; ordinary HTTPS endpoints do not skip TLS inspection.
Subdomains are not implied, so each required hostname is listed explicitly.

To inspect the active presets:

```bash
nemoclaw nv-tech-assistant policy-list
```

The skill can also draft a least-privilege policy for a newly requested source.
It cannot apply that policy from inside the sandbox; review and apply the YAML
from the host.

## Example prompts

- `/nv_tech_assistant recommend an NVIDIA model for speech recognition`
- `/nv_tech_assistant show an official TensorRT-LLM sample`
- `/nv_tech_assistant I'm getting CUDA error: out of memory with Triton`
- `/nv_tech_assistant show a documented customer success story for NVIDIA Riva`
- `/nv_tech_assistant draft a read-only policy for medium.com`

Answers include links to the exact pages retrieved. Code is included only when
needed or requested and is quoted from its identified source.

## Layout

```text
nv-tech-assistant/
├── .env.example                    # NVIDIA inference and optional Brave settings
├── policies/
│   ├── arxiv.yaml                  # arxiv.org and export.arxiv.org
│   ├── github_ext.yaml             # GitHub pages, API, and raw files
│   └── nvidia_ext.yaml             # authorized NVIDIA sources
├── scripts/
│   ├── _lib.sh                     # shared environment and sandbox helpers
│   ├── onboard.sh                  # create/configure the sandbox
│   ├── install.sh                  # apply policies and deploy the skill
│   ├── start.sh                    # start or recover the sandbox
│   └── stop.sh                     # stop while preserving workspace state
└── skills/
    └── nv-tech-assistant/
        ├── SKILL.md
        └── references/
            ├── nvidia-landscape.md
            ├── sources-and-search.md
            ├── nemoclaw-network-policy.md
            └── nemoclaw-policy-template.yaml
```

## Security notes

- The populated `.env` is ignored by Git; never commit API keys.
- NemoClaw stores inference and Brave credentials through OpenShell provider
  plumbing rather than writing raw keys into the sandbox configuration.
- Brave is optional and is the only web-search provider configured by these
  scripts.
- The source policies are read-only and enforce inspected REST methods.
- `scripts/stop.sh` preserves data. Permanent deletion requires the explicit
  `nemoclaw <name> destroy` command.
