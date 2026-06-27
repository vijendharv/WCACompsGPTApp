# Code Review Guidelines

Use this as the review checklist for the WCA Competition Finder repository.

## Review Scope And Efficiency

- Start with the pull request diff and review only changed behavior.
- Read surrounding code only when needed to validate a concrete concern.
- Apply only the guideline sections relevant to the changed files; do not scan
  unrelated modules for pre-existing issues.
- Do not run builds, tests, or broad repository searches during an automated
  code review. CI and the PR validation summary provide that signal.
- Avoid duplicate tool calls and repeated analysis of the same concern.
- Report only actionable, high-confidence bugs, regressions, security issues,
  or explicit violations of this file.
- If no qualifying issues remain, report that result and stop.

## Architecture

Keep the current boundaries clear:

- `networking.py` owns WCA HTTP, retries, pagination, TLS, and caching.
- `competitions.py`, `registrations.py`, and `report.py` own domain behavior.
- `search.py` owns validated structured search results.
- `mcp_server.py` should stay a thin MCP adapter.
- `notify.py` owns Resend email delivery.
- `public/competition-results-widget.html` should render structured output, not
  parse CLI text.

Question changes that move WCA API calls, eligibility rules, or email delivery
into the MCP adapter or widget.

## MCP And Widget Contract

For MCP changes, verify:

- `search_wca_competitions` remains read-only and uses public WCA data.
- `render_competition_results` accepts prepared results and does not refetch.
- `from_date` defaults at request time, not import/server-startup time.
- Tool output stays structured and JSON-ready.
- Errors stay typed with a JSON payload containing `code` and `message`.
- The widget resource keeps its stable `ui://` URI and
  `text/html;profile=mcp-app` MIME type.
- Render tool metadata still includes `ui.resourceUri` and
  `openai/outputTemplate`.

Schema changes should usually update tests, README, local testing docs, and the
widget together.

For widget changes, treat WCA/API values as untrusted display data. Avoid raw
`innerHTML` injection for API-provided strings; prefer text nodes or explicit
escaping.

## Deployment

For deployment changes, verify:

- Hosted servers bind to configured `HOST` and `PORT`.
- Container/Koyeb runs use `HOST=0.0.0.0` so hosted environments can bind all
  interfaces.
- Local testing still works through `localhost` or `127.0.0.1`.
- `/mcp` remains the public MCP route.
- Health checks are lightweight and do not call the WCA API.
- Docker, Koyeb, and docs do not contain personal absolute paths or secrets.

## Email And Secrets

- Do not expose email sending as a read-only MCP tool.
- Do not send email from search or render flows.
- Do not commit real Resend keys.
- Prefer `RESEND_API_KEY` from the environment.
- Require explicit confirmation for future state-changing MCP actions.

## Tests

For code changes, run:

```bash
python -m unittest discover -s tests
python -m compileall wca_comps tests
```

Use `.venv/bin/python` when local Python resolution is uncertain.

New public functions, domain behavior, MCP tool behavior, and deployment
behavior should have corresponding tests or a clear manual verification note.

For documentation-only changes, tests are not required. If any `.py` file or
runtime/deployment config changed, treat it as a code change.

## Style

No formatter or linter is currently configured. Keep edits consistent with the
surrounding code and avoid style-only churn unless a formatter is added.

## Documentation

Update docs when behavior changes:

- `README.md`
- `docs/LOCAL_MCP_TESTING.md`
- `GPT_APP_ARCHITECTURE.md`
- `RECREATE_VENV.md`

Keep documentation portable. Use paths like `path/to/WCACompsGPTApp`, not a
developer-specific home directory.
