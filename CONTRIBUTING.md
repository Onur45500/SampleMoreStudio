# Contributing to SampleMoreStudio

Thanks for helping improve an equal-cost LLM strategy benchmark. This doc covers local setup, tests, and how to extend the harness safely.

## Development setup

**Prerequisites:** Python 3.11+, Node 20+, [Ollama](https://ollama.com) (for local runs).

```powershell
# Windows
.\setup.ps1
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
```

```bash
# Unix
chmod +x setup.sh && ./setup.sh
source .venv/bin/activate
export PYTHONPATH="$(pwd)"
```

Copy `.env.example` → `.env` only if you need API models (`OPENROUTER_API_KEY`). Never commit `.env`.

Pull a model that matches [`config/models.yaml`](config/models.yaml), e.g. `ollama pull qwen2.5:7b-instruct-q4_K_M`.

### Run API + dashboard

```powershell
uvicorn backend.main:app --reload --port 8000
# other terminal
cd frontend && npm run dev
```

## Tests

Budget and answer-extraction unit tests (no GPU required):

```powershell
python scripts/test_budget.py
```

Prefer a short Phase 0 before large sweeps:

```powershell
python scripts/cli.py phase0 --tasks 5 --seeds 1 --budget 512
```

## Extending the project

### Add a model

Edit [`config/models.yaml`](config/models.yaml). Use `ollama/<name>` for local models. Set `enabled: true` for sweeps.

### Add a task

Drop a JSON file under `tasks/phase1_reasoning/<category>/` or `tasks/phase2_agent/<category>/`:

```json
{
  "id": "math_999",
  "category": "math",
  "prompt": "...",
  "answer": "42",
  "grader": "numeric_tolerance",
  "grader_params": { "tolerance": 0.01 },
  "metadata": {}
}
```

Graders: `numeric_tolerance`, `exact_match`, `regex`, `code_tests`, `tool_answer`. Phase 2 tool tasks need `metadata.tool_kind` (`file` | `json` | `calc`) and matching fixture data.

Or regenerate suites:

```powershell
python scripts/cli.py generate-tasks
```

### Add a strategy

1. Implement `Strategy` in `backend/strategies/phase1/` or `phase2/` (see [`backend/strategies/base.py`](backend/strategies/base.py)).
2. Respect the completion-token budget via [`backend/token_budget.py`](backend/token_budget.py) — never silently exceed `B`.
3. Register in [`config/strategies.yaml`](config/strategies.yaml) and [`backend/strategy_registry.py`](backend/strategy_registry.py).
4. Document the budget split formula in the PR description (and README if it changes the public methodology).

## Coding notes

- Prefer **named exports** in service/hook-style Python modules; keep Next-style defaults only where the stack requires them (this repo is FastAPI + Vite, not Next).
- Avoid `any` in TypeScript; use `unknown` + narrowing.
- Do not commit secrets, API keys, or large binary model weights.
- `results/*.db` and transcripts are gitignored — don’t force-add them with credentials or private API logs.
- Code task grading uses subprocess + timeout; it is **not** a security sandbox. Only add trusted tests.

## Pull requests

1. Keep PRs focused (one strategy, one task suite, or one docs/UX fix).
2. Mention how you validated (unit tests, Phase 0 subset, screenshot of dashboard if UI).
3. If you change budget formulas, update README methodology and add/adjust `scripts/test_budget.py`.
4. If you publish new numbers, mark sample size, model id, budget, and seeds — and prefer bootstrap CIs for Δpp.

## Code of conduct

Be respectful in issues and PRs. This is a research tooling project; debate the methodology with evidence (transcripts, budget integrity, truncation rates), not vibes alone.

## License

By contributing, you agree your contributions are licensed under the MIT License ([LICENSE](LICENSE)).
