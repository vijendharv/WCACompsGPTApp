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
| `wca_comps/competitions.py`  | Fetch upcoming competitions and filter them by region.          |
| `wca_comps/registrations.py` | Check a person's registration via the public WCIF endpoint.     |
| `wca_comps/report.py`        | Orchestrate the services, compute eligibility, render output.   |
| `wca_comps/notify.py`        | **Email** — send the report via the Resend HTTP API.            |
| `wca_comps/cli.py`           | Command-line entrypoint wiring everything together.             |

Dependencies flow one way: `cli → report → {competitions, registrations} →
networking`. Only `networking` touches the network, so the rest is easy to test
and reuse.

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
