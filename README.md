# WCA Competition Finder

Finds upcoming [World Cube Association](https://www.worldcubeassociation.org/)
competitions across all U.S. states and Canadian provinces/territories and
checks whether a given competitor (default: *Saharsh Sai Vontela*, WCA ID
`2023VONT01`) is registered for them. Searches default to **Washington**,
**Oregon**, and **British Columbia** when no regions are supplied.

The canonical ChatGPT app icon is stored at
[`assets/wca-competition-finder-icon.png`](assets/wca-competition-finder-icon.png).
Use this version for app configuration and submission so the branding remains
consistent across environments.

It uses the public WCA API:

- `GET /api/v0/competitions` — upcoming competitions (filtered by country, then
  by state/province client-side since the API has no sub-country filter).
- `GET /api/v0/competitions/{id}/wcif/public` — the public WCIF document, whose
  `persons` list reveals who is registered and their registration status.

## Module layout

The code is decomposed into small, single-responsibility modules:

| Module                  | Responsibility                                                        |
| ----------------------- | --------------------------------------------------------------------- |
| `wca_comps/config.py`        | Static config: API URL, target regions, default person.         |
| `wca_comps/networking.py`    | **Networking** — HTTP client (GET, retries, pagination, TLS).   |
| `wca_comps/models.py`        | Typed data classes for API entities + parsing helpers.          |
| `wca_comps/validation.py`    | Runtime validation for WCA IDs, dates, and supported regions.   |
| `wca_comps/serializers.py`   | Stable JSON-ready result schemas for app/MCP consumers.         |
| `wca_comps/search.py`        | Validated structured search workflow for MCP tools.             |
| `wca_comps/mcp_server.py`    | Read-only MCP server exposing search/render tools and widget resource. |
| `wca_comps/errors.py`        | Typed application errors for validation, no results, upstreams. |
| `wca_comps/competitions.py`  | Fetch upcoming competitions and filter them by region.          |
| `wca_comps/registrations.py` | Check a person's registration via the public WCIF endpoint.     |
| `wca_comps/report.py`        | Orchestrate the services, compute eligibility, render output.   |
| `wca_comps/notify.py`        | **Email** — send the report via the Resend HTTP API.            |
| `wca_comps/cli.py`           | Command-line entrypoint wiring everything together.             |

Dependencies stay layered so the CLI and MCP adapter reuse the same core:
`cli → report → {competitions, registrations} → networking` for human-readable
reports, and `mcp_server → search → report → {competitions, registrations} →
networking` for structured tool results. WCA API access is isolated in
`networking`; Resend email delivery is isolated in `notify`.

## Current core behavior

The CLI prints a human-readable report, while `wca_comps.search` provides the
structured workflow used by the MCP server.

Important details:

- `from_date` is optional. When it is omitted or `None`, the current date is
  resolved at request/runtime, not at server startup or module import time.
- WCA IDs are normalized to uppercase and must match the WCA ID format, for
  example `2023VONT01`.
- Supported regions include all 50 U.S. states, the District of Columbia, all
  10 Canadian provinces, and all 3 Canadian territories. Full names and postal
  abbreviations are matched case-insensitively. Omitted regions default to
  `Washington`, `Oregon`, and `British Columbia`.
- Competition list and public WCIF responses are cached for 60 seconds by
  default in `WCAClient`. Pass `cache_ttl_seconds=0` to disable caching, such
  as in tests or freshness debugging.
- WCIF registration checks are fetched concurrently by `build_assessments`,
  which keeps the final competition order stable while reducing total latency.
- Deleted registrations are not grouped as "Already registered"; they are
  assessed by the normal registration-window eligibility rules.
- Structured output includes the original query, summary counts, grouped
  results, and a flat `competitions` list.

Example structured search call:

```python
from wca_comps.search import search_competitions

payload = search_competitions(
    wca_id="2023VONT01",
    person_name="Saharsh Sai Vontela",
    regions=["Washington", "Oregon", "British Columbia"],
    from_date=None,
)
```

For example, `regions=["California", "ON", "Québec"]` searches California,
Ontario, and Quebec. Exact subdivision matching prevents names such as
`Virginia` from also matching `West Virginia`. Use `regions=["United States"]`
or `regions=["Canada"]` to search every supported subdivision in that country.

The returned payload is JSON-ready and backs the `search_wca_competitions` MCP
tool. If no matching competitions are found, the structured search path raises
a typed no-results error instead of returning an empty successful payload.

## MCP server

The project includes a read-only MCP server using the official Python `mcp`
SDK. It currently implements the read-only MVP pieces from milestones 2 and 3:
one data-search tool, one widget-render tool, and one registered ChatGPT Apps
widget resource.

| Tool | Purpose |
| --- | --- |
| `search_wca_competitions` | Find upcoming WCA competitions in supported regions and assess public registration/eligibility for a WCA ID. |
| `render_competition_results` | Render a prepared `search_wca_competitions` result as responsive grouped competition cards. |

Registered resource:

| Resource | MIME type | Purpose |
| --- | --- | --- |
| `ui://widget/competition-results-v1.html` | `text/html;profile=mcp-app` | ChatGPT Apps widget template that renders grouped competition result cards from `render_competition_results`. |

Tool behavior:

- `search_wca_competitions` takes `wca_id`, optional `person_name`, optional
  `regions`, and optional `from_date`.
- `regions` accepts U.S. state and Canadian province/territory names or postal
  abbreviations; omitted regions retain the Pacific Northwest defaults.
- `from_date` defaults at request time when omitted or `null`.
- `search_wca_competitions` is annotated with `readOnlyHint: true` and
  `openWorldHint: true`.
- `render_competition_results` takes a prepared structured search result and
  does not refetch WCA data.
- `render_competition_results` points to the registered widget resource at
  `ui://widget/competition-results-v1.html` through both `ui.resourceUri` and
  `openai/outputTemplate`.
- The widget resource advertises Apps SDK metadata, a deployment-specific
  domain from `WIDGET_DOMAIN` when configured, a border preference, a CSP, and
  allowed redirects to
  `https://www.worldcubeassociation.org` for official competition links.
- Results use a structured output schema with `query`, `summary`, `groups`,
  and `competitions`.
- Validation, no-result, and upstream failures are returned as typed MCP tool
  errors with a JSON payload containing at least `code` and `message`.

Run over stdio for local MCP Inspector usage:

```bash
python -m wca_comps.mcp_server
```

Run the Streamable HTTP endpoint at `/mcp`:

```bash
MCP_TRANSPORT=streamable-http HOST=127.0.0.1 PORT=8000 python -m wca_comps.mcp_server
```

In HTTP mode, `GET /health` returns `{"status":"ok"}` without contacting the
WCA API. Hosted environments must set `HOST=0.0.0.0`; local clients can still
connect through `localhost` or `127.0.0.1`.

The module also exports `app` for ASGI servers and `create_mcp_server()` for
tests or custom hosting.

For step-by-step local testing, see
[`docs/LOCAL_MCP_TESTING.md`](docs/LOCAL_MCP_TESTING.md).
For ChatGPT conversation and widget test cases, see
[`docs/GPT_APP_TEST_PROMPTS.md`](docs/GPT_APP_TEST_PROMPTS.md).

> MCP Inspector can show the registered resource and tool metadata, including
> the widget URI, but depending on the Inspector version it may not render the
> ChatGPT iframe preview exactly like ChatGPT Developer Mode.

## ChatGPT widget

The widget HTML lives at
[`public/competition-results-widget.html`](public/competition-results-widget.html)
and is served by the MCP resource above.

Current widget behavior:

- Reads structured output from `window.openai.toolOutput` when rendered by
  ChatGPT, listens for `openai:set_globals` updates when output arrives after
  iframe initialization, and uses a small local fallback sample for standalone
  development.
- Advertises the widget as the complete user-facing result so ChatGPT avoids
  repeating the same competition table unless the user requests text.
- Shows grouped competition cards for registered, available, and unavailable
  competitions.
- Includes category tabs and a region filter.
- Displays dates, venue/location, events, registration windows, competitor
  counts, capacity, and eligibility reasons.
- Opens official WCA competition links through the Apps SDK bridge when
  available.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> `truststore` is included so verification works behind corporate
> TLS-intercepting proxies by using the OS trust store. It is optional — the
> client falls back to `certifi` if it is unavailable.

If the repository is moved or `.venv/bin/pip` points at another checkout,
repair or recreate the virtualenv from the repo root. See
[`RECREATE_VENV.md`](RECREATE_VENV.md) for the full steps.

## Docker

Build the production image from the repository root:

```bash
docker build -t wca-comps-mcp .
```

Run it locally:

```bash
docker run --rm --name wca-comps-mcp -p 8000:8000 wca-comps-mcp
```

The container defaults to Streamable HTTP on `0.0.0.0:8000`. Verify it from
another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Use `http://127.0.0.1:8000/mcp` as the Streamable HTTP URL in MCP Inspector.
The image runs as a non-root user and reads `MCP_TRANSPORT`, `HOST`, and `PORT`
from the environment, so a hosting provider can override them.

When testing is complete, press `Ctrl-C` in the terminal running the container.
Because the command uses `--rm`, Docker removes the stopped container
automatically. If it is running in another terminal, use:

```bash
docker stop wca-comps-mcp
```

To remove the local image and rebuild everything without cached layers:

```bash
docker image rm wca-comps-mcp
docker build --no-cache -t wca-comps-mcp .
```

For the Koyeb service configuration and ChatGPT connection flow, see
[`docs/KOYEB_DEPLOYMENT.md`](docs/KOYEB_DEPLOYMENT.md).

## Usage

```bash
# Defaults to Saharsh Sai Vontela (2023VONT01), today onward
python -m wca_comps.cli

# Check a different competitor
python -m wca_comps.cli --wca-id 2018MACK04 --name "Shaun Mack"

# Only competitions starting on/after a date
python -m wca_comps.cli --from-date 2026-08-01

# Also email the report (in addition to printing it)
python -m wca_comps.cli --email-to vontelav@gmail.com

# Search other supported regions; repeat --region as needed
python -m wca_comps.cli --region California --region ON
```

Output is grouped into **Already registered**, **Can register (open, not yet
registered)**, and **Not currently registerable**, with dates, venue, events,
competitor counts, registration windows, and links for each competition.

Invalid input exits with status code `2` and prints a validation message. WCA
API failures exit with status code `1`.

## Testing

The project uses the standard-library `unittest` runner for the current core
tests.

```bash
python -m unittest discover -s tests
python -m compileall wca_comps tests
```

The tests cover input validation, runtime date defaults, supported region
selection, short-lived caching, concurrent WCIF lookup, structured grouping
behavior, MCP tool schemas/annotations/error handling, widget resource
registration, render-tool behavior, hosted address configuration, and the
health endpoint.

## Pull request review

Pull requests run the `Code Review` GitHub Actions workflow when opened or
updated. The workflow requires the repository secret `ANTHROPIC_API_KEY`,
reviews only the pull request changes with a single Haiku agent, and posts one
concise result comment. See
[`docs/CLAUDE_CODE_REVIEW.md`](docs/CLAUDE_CODE_REVIEW.md) for the workflow,
cost controls, troubleshooting, and lessons learned.

## Milestone status

Completed:

- Milestone 1: structured application core, validation, concurrency, caching,
  serializers, and tests.
- Milestone 2: read-only MCP server with `search_wca_competitions`, typed
  errors, schemas, and annotations.
- Milestone 3: ChatGPT widget resource and `render_competition_results` tool.

In progress:

- Milestone 4: the production Dockerfile, non-root container process, and
  lightweight health endpoint are implemented. Koyeb deployment, public HTTPS
  verification, ChatGPT Developer Mode connection, and cold-start measurements
  remain.

Not yet implemented:

- Milestone 5: confirmed email action exposed as an MCP tool.
- Milestone 6: public release assets, policy/support URLs, acceptance tests,
  and submission flow.

## Emailing the report

Passing `--email-to <address>` also delivers the report by email via
[Resend](https://resend.com), sent as formatted HTML (with the plain-text
report as a fallback). The API key is resolved in this order:

1. the `RESEND_API_KEY` environment variable (preferred), or
2. the `RESEND_API_KEY_FALLBACK` constant in `wca_comps/config.py`.

```bash
export RESEND_API_KEY=re_your_key_here
python -m wca_comps.cli --email-to vontelav@gmail.com
```

> Without a verified custom domain, Resend sends from its shared
> `onboarding@resend.dev` sender and only delivers to your Resend
> account-owner email address.

> **Security:** do not commit a real API key. Prefer the environment variable,
> and if you use the hardcoded fallback, rotate the key before pushing to a
> shared or public repository.
