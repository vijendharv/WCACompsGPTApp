# Koyeb Deployment

Use this guide after the Milestone 4 deployment changes are merged into
`master`. It deploys the MCP server as a Koyeb Web Service and connects the
public HTTPS endpoint to ChatGPT Developer Mode.

## 1. Verify The Production Image Locally

From the repository root:

```bash
docker build -t wca-comps-mcp .
docker run --rm --name wca-comps-mcp -p 8000:8000 wca-comps-mcp
```

From another terminal:

```bash
curl -i http://127.0.0.1:8000/health
```

The response should have status `200` and contain:

```json
{"status":"ok"}
```

Connect MCP Inspector to `http://127.0.0.1:8000/mcp` and confirm that both
tools and the widget resource are available.

When finished, press `Ctrl-C` in the terminal running the container. The
`--rm` option removes it automatically. If it is running in another terminal,
use:

```bash
docker stop wca-comps-mcp
```

To reset the local image before another clean test:

```bash
docker rm -f wca-comps-mcp 2>/dev/null || true
docker image rm wca-comps-mcp 2>/dev/null || true
docker build --no-cache -t wca-comps-mcp .
```

Continue to Koyeb only after the rebuilt image passes the health and MCP checks.

## 2. Create A Koyeb Account

1. Open [Koyeb](https://app.koyeb.com/auth/signup) and create an account.
2. Sign in to the Koyeb control panel.
3. Select **Create Web Service** and choose **GitHub** as the deployment method.
4. Install the Koyeb GitHub App when prompted.
5. Grant it access to the `WCACompsGPTApp` repository.

Repository-only GitHub access is sufficient. Koyeb documents the current
GitHub connection flow in its
[Deploy with GitHub guide](https://www.koyeb.com/docs/build-and-deploy/deploy-with-git).

## 3. Configure The Web Service

Use these values in the Koyeb service form:

| Setting | Value |
| --- | --- |
| Repository | `WCACompsGPTApp` |
| Branch | `master` |
| Builder | Dockerfile |
| Service type | Web Service |
| Instance | Free |
| Exposed port | `8000` |
| Protocol | HTTP |
| Public route | `/` |

Add these environment variables:

```text
MCP_TRANSPORT=streamable-http
HOST=0.0.0.0
PORT=8000
WIDGET_DOMAIN=https://YOUR-SERVICE-DOMAIN
```

Set `WIDGET_DOMAIN` to the public HTTPS origin assigned to this Koyeb service,
without a trailing path. The widget domain is deployment-specific and required
for ChatGPT app submission.

Configure a custom health check:

```text
Protocol: HTTP
Path: /health
```

Select an available region near the expected users and leave automatic
deployment enabled for `master`. Do not add `RESEND_API_KEY` for Milestone 4;
the current MCP tools do not send email.

Deploy the service and wait until Koyeb reports the deployment as healthy. If
it fails, inspect the build logs, runtime logs, and Instance health-check
message before changing the configuration.

## 4. Verify The Public Endpoint

Copy the public Koyeb domain and test the health endpoint:

```bash
curl -i https://YOUR-SERVICE-DOMAIN/health
```

Start MCP Inspector locally:

```bash
npx @modelcontextprotocol/inspector
```

In Inspector, select **Streamable HTTP** and connect to:

```text
https://YOUR-SERVICE-DOMAIN/mcp
```

Confirm that Inspector can:

1. List `search_wca_competitions` and `render_competition_results`.
2. List and read `ui://widget/competition-results-v1.html`.
3. Run a live competition search.
4. Pass the structured search result to the render tool.

No local MCP server is needed for this test. Inspector connects directly to
the Koyeb deployment.

## 5. Connect ChatGPT

1. In ChatGPT, open **Settings -> Apps & Connectors -> Advanced settings**.
2. Enable **Developer mode** if the workspace allows it.
3. Return to **Settings -> Apps & Connectors** and select **Create**.
4. Enter a name and a concise description of the WCA competition finder.
5. Set the connector URL to `https://YOUR-SERVICE-DOMAIN/mcp`.
6. Create the connector and verify that ChatGPT discovers both tools.
7. Start a new chat, add the connector from the composer, and request upcoming
   WCA competitions.
8. Verify the result data, official WCA links, and widget rendering.

See OpenAI's current
[Connect from ChatGPT guide](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt)
if the settings labels or connection flow change.

## 6. Record Cold-Start Behavior

The Free Instance can sleep after inactivity. Record at least:

1. Health and MCP response latency immediately after deployment.
2. First-request latency after the service has entered its sleeping state.
3. A second request immediately afterward to capture warm latency.
4. Any transient errors shown by ChatGPT or MCP Inspector during wake-up.

Add the observed timings and test date to this document after deployment. Do
not claim an uptime or cold-start threshold until it has been measured.
