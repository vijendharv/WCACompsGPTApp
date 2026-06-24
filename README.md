# WCA Competition Finder

Finds upcoming [World Cube Association](https://www.worldcubeassociation.org/)
competitions in **Washington**, **Oregon**, and **British Columbia** and checks
whether a given competitor (default: *Saharsh Sai Vontela*, WCA ID `2023VONT01`)
is registered for them.

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
| `wca_comps/mcp_server.py`    | Read-only MCP server exposing `search_wca_competitions`.        |
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
- Supported regions are currently `Washington`, `Oregon`, and
  `British Columbia`; region names are matched case-insensitively.
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

The returned payload is JSON-ready and backs the `search_wca_competitions` MCP
tool.

## MCP server

The project includes a read-only MCP server using the official Python `mcp`
SDK. It exposes two tools:

| Tool | Purpose |
| --- | --- |
| `search_wca_competitions` | Find upcoming WCA competitions in supported regions and assess public registration/eligibility for a WCA ID. |
| `render_competition_results` | Render a prepared `search_wca_competitions` result as responsive grouped competition cards. |

Tool behavior:

- `search_wca_competitions` takes `wca_id`, optional `person_name`, optional
  `regions`, and optional `from_date`.
- `from_date` defaults at request time when omitted or `null`.
- `search_wca_competitions` is annotated with `readOnlyHint: true` and
  `openWorldHint: true`.
- `render_competition_results` takes a prepared structured search result and
  does not refetch WCA data.
- `render_competition_results` points to the registered widget resource at
  `ui://widget/competition-results-v1.html`.
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
MCP_TRANSPORT=streamable-http PORT=8000 python -m wca_comps.mcp_server
```

The module also exports `app` for ASGI servers and `create_mcp_server()` for
tests or custom hosting.

For step-by-step local testing, see
[`docs/LOCAL_MCP_TESTING.md`](docs/LOCAL_MCP_TESTING.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> `truststore` is included so verification works behind corporate
> TLS-intercepting proxies by using the OS trust store. It is optional — the
> client falls back to `certifi` if it is unavailable.

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
behavior, and the MCP tool schema/annotations/error handling.

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
