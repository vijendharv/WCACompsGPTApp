# GPT App Test Prompts

Use these prompts in a new ChatGPT conversation with **WCA Competition
Finder** enabled. WCA competition and registration data changes over time, so
verify behavior and result structure rather than exact counts.

## Basic Search

```text
Find upcoming WCA competitions in Washington, Oregon, and British Columbia for WCA ID 2023VONT01, starting today.
```

Verify that the app searches all three supported regions and reports registered,
available, and unavailable competitions.

## Single-Region Search

```text
Show upcoming WCA competitions in Washington for WCA ID 2023VONT01.
```

Verify that every returned competition is in Washington.

## Registration Status

```text
Which upcoming competitions is WCA ID 2023VONT01 already registered for, and which ones can they still register for?
```

Verify that the response distinguishes existing registrations from competitions
where registration is available.

## Eligibility Explanation

```text
Find upcoming competitions in Oregon for WCA ID 2023VONT01 and explain why each competition is or is not currently open to them.
```

Verify that each result includes a human-readable eligibility reason.

## Date Filtering

```text
Find WCA competitions in British Columbia for WCA ID 2023VONT01 starting 30 days from today.
```

Verify that ChatGPT resolves the requested date and that no returned competition
starts before it.

## Widget Rendering

```text
Find upcoming WCA competitions in Washington for WCA ID 2023VONT01, then display the complete search result using the competition results widget.
```

Verify that ChatGPT first runs `search_wca_competitions`, passes its complete
structured result to `render_competition_results`, and displays grouped cards.

## Invalid WCA ID

```text
Find upcoming competitions for WCA ID INVALID123.
```

Verify that the app reports a clear WCA ID validation error instead of returning
results or exposing an internal traceback.

## Unsupported Region

```text
Find upcoming WCA competitions in California for WCA ID 2023VONT01.
```

Verify that the app explains that the supported regions are Washington, Oregon,
and British Columbia.

## No Results

```text
Find WCA competitions in Washington for WCA ID 2023VONT01 starting on 2100-01-01.
```

Verify that the app reports that no matching competitions were found and does
not fabricate results.

## Missing Required Information

```text
Find upcoming WCA competitions in Washington for me.
```

Verify that ChatGPT asks for a WCA ID before searching.

## Suggested Test Order

1. Run Basic Search to confirm public WCA API access.
2. Run Widget Rendering to confirm the search-to-render handoff.
3. Run Single-Region Search and Date Filtering to verify filters.
4. Run Registration Status and Eligibility Explanation to inspect result quality.
5. Run the invalid, unsupported-region, no-results, and missing-input prompts to
   verify error handling.

