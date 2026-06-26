# Local MCP Testing

Use this guide to run and test the WCA Competition Finder MCP server locally.

## 1. Start From Latest Master

```bash
cd path/to/WCACompsGPTApp
git switch master
git pull --ff-only origin master
```

## 2. Prepare The Virtualenv

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `.venv/bin/pip` points at another checkout, repair the virtualenv from the
repo root:

```bash
python3 -m venv --upgrade .venv
.venv/bin/python -m pip install --force-reinstall pip
```

Confirm it resolves inside this repo:

```bash
.venv/bin/pip --version
```

The path should include:

```text
WCACompsGPTApp/.venv/
```

## 3. Run Automated Tests

```bash
python -m unittest discover -s tests
```

Expected result:

```text
Ran 14 tests
OK
```

You can also run the compile check:

```bash
python -m compileall wca_comps tests
```

## 4. Smoke-Test MCP Registration

```bash
python - <<'PY'
import asyncio
from wca_comps.mcp_server import create_mcp_server

async def main():
    server = create_mcp_server()

    print("Tools:")
    tools = await server.list_tools()
    for tool in tools:
        print(tool.name)
        print(tool.annotations.model_dump() if tool.annotations else None)
        print(tool.meta)

    print("Resources:")
    resources = await server.list_resources()
    for resource in resources:
        print(resource.name)
        print(resource.uri)
        print(resource.mimeType)
        print(resource.meta)

asyncio.run(main())
PY
```

Expected output should include:

```text
search_wca_competitions
render_competition_results
competition_results_widget
ui://widget/competition-results-v1.html
text/html;profile=mcp-app
```

The search tool annotations should include `readOnlyHint: true` and
`openWorldHint: true`. The render tool metadata should include
`openai/outputTemplate` and `ui.resourceUri` pointing to the widget resource.
The resource should use the `text/html;profile=mcp-app` MIME type and include
widget metadata/CSP.

## 5. Run Stdio Mode

Stdio mode is best for MCP Inspector and local tool-contract checks:

```bash
python -m wca_comps.mcp_server
```

This command appears to hang because the server is waiting for MCP JSON-RPC
messages over stdio. That is normal.

If you run MCP Inspector with the command in the next section, you do not need
to start this stdio process separately. Inspector launches the stdio server for
you. If you did start it manually, stop it with `Ctrl-C` before starting a
different server mode.

## 6. Test With MCP Inspector

From another terminal in the repo:

```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m wca_comps.mcp_server
```

Open the local URL printed by Inspector, then:

1. Go to the tools view.
2. Select `search_wca_competitions`.
3. Switch the input editor to JSON if Inspector is showing form fields.
4. Use this sample payload:

```json
{
  "wca_id": "2023VONT01",
  "person_name": "Saharsh Sai Vontela",
  "regions": ["Washington", "Oregon", "British Columbia"],
  "from_date": null
}
```

The result should contain:

- `query`
- `summary`
- `groups`
- `competitions`

This call reaches the live public WCA API.

To inspect the registered widget resource:

1. Go to the resources view.
2. Select `competition_results_widget`.
3. Confirm the response includes `ui://widget/competition-results-v1.html`.
4. Confirm the MIME type is `text/html;profile=mcp-app`.
5. Confirm the returned text starts with HTML for the widget template.

To test the widget, copy the structured result from `search_wca_competitions`
and call `render_competition_results` with:

```json
{
  "prepared_result": {
    "query": {
      "wca_id": "2023VONT01",
      "person_name": "Saharsh Sai Vontela",
      "regions": ["Washington"],
      "from_date": "2026-08-01"
    },
    "summary": {
      "total": 0,
      "registered": 0,
      "available": 0,
      "unavailable": 0
    },
    "groups": {
      "registered": [],
      "available": [],
      "unavailable": []
    },
    "competitions": []
  }
}
```

For a full visual test, replace the minimal object with the actual search
result. Inspector should show the registered widget template at
`ui://widget/competition-results-v1.html`. Depending on the Inspector version,
it may show the resource and tool metadata without rendering the same iframe
preview that ChatGPT Developer Mode renders.

## 7. Run Streamable HTTP Mode

Streamable HTTP mode exposes the hosted-style `/mcp` endpoint:

```bash
MCP_TRANSPORT=streamable-http HOST=127.0.0.1 PORT=8000 python -m wca_comps.mcp_server
```

The local endpoint is:

```text
http://127.0.0.1:8000/mcp
```

In MCP Inspector, choose Streamable HTTP and use that URL.

The health endpoint is available only in HTTP mode. From another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Do not run the stdio server and Streamable HTTP server as the same process.
Stop the stdio process and its Inspector session before switching to Streamable
HTTP. Start a new Inspector session only if you want to inspect the HTTP
endpoint.

## 8. Test The Production Container

Docker must be installed and running. From the repository root, build the
image:

```bash
docker build -t wca-comps-mcp .
```

Start the container:

```bash
docker run --rm --name wca-comps-mcp -p 8000:8000 wca-comps-mcp
```

The image already sets `MCP_TRANSPORT=streamable-http`, `HOST=0.0.0.0`, and
`PORT=8000`. From another terminal, verify the health endpoint:

```bash
curl -i http://127.0.0.1:8000/health
```

Then connect MCP Inspector to:

```text
http://127.0.0.1:8000/mcp
```

To inspect Docker's own health status while the named container is running:

```bash
docker inspect --format '{{json .State.Health}}' wca-comps-mcp
```

Stop the attached container with `Ctrl-C`. The `--rm` option removes it after
it stops.

## 9. CLI Sanity Check

The CLI path is separate from MCP, but it is useful for confirming the core WCA
logic still works:

```bash
python -m wca_comps.cli
```

This prints the normal report and does not email unless `--email-to` is passed.

## Troubleshooting

- **`python -m wca_comps.mcp_server` appears stuck:** expected in stdio mode.
  Use MCP Inspector to send requests.
- **`ModuleNotFoundError: mcp`:** run `python -m pip install -r requirements.txt`
  inside the activated virtualenv.
- **WCA API DNS or network errors:** local network access is required for live
  searches.
- **Unexpected `.venv` path:** check `.venv/bin/pip --version` and repair the
  virtualenv with the commands in step 2.
- **Docker port already allocated:** stop the existing process on port 8000 or
  run the container with matching alternate ports, such as
  `docker run --rm -e PORT=8080 -p 8080:8080 wca-comps-mcp`.
