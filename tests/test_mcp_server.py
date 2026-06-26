from __future__ import annotations

import asyncio
import json
import os
import unittest
from unittest.mock import patch

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from wca_comps.errors import InputValidationError
from wca_comps.mcp_server import (
    WIDGET_MIME_TYPE,
    WIDGET_RESOURCE_URI,
    create_mcp_server,
    search_wca_competitions_handler,
)


class MCPServerTests(unittest.TestCase):
    def test_health_endpoint_reports_process_health(self) -> None:
        async def run() -> None:
            app = create_mcp_server().streamable_http_app()
            transport = httpx.ASGITransport(app=app)

            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.get("/health")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

        asyncio.run(run())

    def test_server_uses_configured_host_and_port(self) -> None:
        with patch.dict(
            os.environ,
            {"HOST": "0.0.0.0", "PORT": "9000"},
        ):
            server = create_mcp_server()

        self.assertEqual(server.settings.host, "0.0.0.0")
        self.assertEqual(server.settings.port, 9000)

    def test_search_tool_schema_and_annotations(self) -> None:
        async def run() -> None:
            server = create_mcp_server()
            tools = await server.list_tools()

            self.assertEqual(len(tools), 2)
            tool = next(tool for tool in tools if tool.name == "search_wca_competitions")
            self.assertEqual(tool.name, "search_wca_competitions")
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertTrue(tool.annotations.openWorldHint)
            self.assertIsNone(tool.meta)
            self.assertIn("wca_id", tool.inputSchema["properties"])
            self.assertIn("from_date", tool.inputSchema["properties"])
            self.assertIn("summary", tool.outputSchema["properties"])
            self.assertIn("groups", tool.outputSchema["properties"])
            self.assertIn("competitions", tool.outputSchema["properties"])

        asyncio.run(run())

    def test_render_tool_schema_and_widget_metadata(self) -> None:
        async def run() -> None:
            server = create_mcp_server()
            tools = await server.list_tools()

            tool = next(tool for tool in tools if tool.name == "render_competition_results")
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertFalse(tool.annotations.openWorldHint)
            self.assertEqual(tool.meta["ui"]["resourceUri"], WIDGET_RESOURCE_URI)
            self.assertEqual(tool.meta["openai/outputTemplate"], WIDGET_RESOURCE_URI)
            self.assertIn("prepared_result", tool.inputSchema["properties"])
            self.assertIn("summary", tool.outputSchema["properties"])

        asyncio.run(run())

    def test_widget_resource_is_registered(self) -> None:
        async def run() -> None:
            server = create_mcp_server()
            resources = await server.list_resources()

            resource = next(
                resource for resource in resources if str(resource.uri) == WIDGET_RESOURCE_URI
            )
            self.assertEqual(resource.mimeType, WIDGET_MIME_TYPE)
            self.assertTrue(resource.meta["ui"]["prefersBorder"])
            self.assertEqual(
                resource.meta["openai/widgetCSP"]["redirect_domains"],
                ["https://www.worldcubeassociation.org"],
            )

            contents = await server.read_resource(WIDGET_RESOURCE_URI)
            self.assertEqual(contents[0].mime_type, WIDGET_MIME_TYPE)
            self.assertIn("window.openai?.toolOutput", contents[0].content)
            self.assertIn("Registration open", contents[0].content)

        asyncio.run(run())

    def test_search_tool_returns_structured_content(self) -> None:
        async def run() -> None:
            server = create_mcp_server()
            with patch(
                "wca_comps.mcp_server.search_competitions",
                return_value=_sample_payload(),
            ):
                content, structured = await server.call_tool(
                    "search_wca_competitions",
                    {
                        "wca_id": "2023VONT01",
                        "regions": ["Washington"],
                        "from_date": "2026-08-01",
                    },
                )

            self.assertEqual(structured["summary"]["total"], 1)
            self.assertEqual(
                structured["competitions"][0]["competition"]["id"], "FakeComp2026"
            )
            self.assertEqual(json.loads(content[0].text), structured)

        asyncio.run(run())

    def test_render_tool_returns_prepared_result_without_refetching(self) -> None:
        async def run() -> None:
            server = create_mcp_server()
            with patch("wca_comps.mcp_server.search_competitions") as search:
                content, structured = await server.call_tool(
                    "render_competition_results",
                    {"prepared_result": _sample_payload()},
                )

            search.assert_not_called()
            self.assertEqual(structured["summary"]["total"], 1)
            self.assertEqual(json.loads(content[0].text), structured)

        asyncio.run(run())

    def test_handler_converts_validation_errors_to_typed_tool_errors(self) -> None:
        with patch(
            "wca_comps.mcp_server.search_competitions",
            side_effect=InputValidationError("wca_id", "must be valid"),
        ):
            with self.assertRaises(ToolError) as raised:
                search_wca_competitions_handler(wca_id="bad")

        payload = json.loads(str(raised.exception))
        self.assertEqual(payload["code"], "invalid_input")
        self.assertEqual(payload["field"], "wca_id")


def _sample_payload() -> dict:
    assessment = {
        "competition": {
            "id": "FakeComp2026",
            "name": "Fake Comp 2026",
            "start_date": "2026-08-01",
            "end_date": "2026-08-01",
            "location": "Seattle, Washington",
            "venue": "Fake Venue",
            "url": "https://www.worldcubeassociation.org/competitions/FakeComp2026",
            "region": "Washington",
            "event_ids": ["333"],
            "registration_open": "2026-06-01T00:00:00+00:00",
            "registration_close": "2026-07-25T00:00:00+00:00",
            "competitor_limit": 100,
        },
        "registration": {
            "is_registered": False,
            "status": None,
            "event_ids": [],
            "competitor_count": 50,
        },
        "eligibility": {
            "registration_state": "open",
            "can_register": True,
            "reason": "Open - 50 spot(s) left (50/100)",
        },
    }
    return {
        "query": {
            "wca_id": "2023VONT01",
            "person_name": "Saharsh Sai Vontela",
            "regions": ["Washington"],
            "from_date": "2026-08-01",
        },
        "summary": {
            "total": 1,
            "registered": 0,
            "available": 1,
            "unavailable": 0,
        },
        "groups": {
            "registered": [],
            "available": [assessment],
            "unavailable": [],
        },
        "competitions": [assessment],
    }


if __name__ == "__main__":
    unittest.main()
