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
Ran 9 tests
OK
```

You can also run the compile check:

```bash
python -m compileall wca_comps tests
```

## 4. Smoke-Test MCP Tool Registration

```bash
python - <<'PY'
import asyncio
from wca_comps.mcp_server import create_mcp_server

async def main():
    server = create_mcp_server()
    tools = await server.list_tools()
    tool = tools[0]
    print(tool.name)
    print(tool.annotations.model_dump())
    print(sorted(tool.outputSchema["properties"].keys()))

asyncio.run(main())
PY
```

Expected output should include:

```text
search_wca_competitions
['competitions', 'groups', 'query', 'summary']
```

The annotations should include `readOnlyHint: true` and `openWorldHint: true`.

## 5. Run Stdio Mode

Stdio mode is best for MCP Inspector and local tool-contract checks:

```bash
python -m wca_comps.mcp_server
```

This command appears to hang because the server is waiting for MCP JSON-RPC
messages over stdio. That is normal.

## 6. Test With MCP Inspector

From another terminal in the repo:

```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m wca_comps.mcp_server
```

Open the local URL printed by Inspector, then:

1. Go to the tools view.
2. Select `search_wca_competitions`.
3. Use this sample payload:

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

## 8. CLI Sanity Check

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
