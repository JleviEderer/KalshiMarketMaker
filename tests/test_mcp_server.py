import json
import socketserver
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class _KalshiFixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        payload = self.server.routes.get(parsed.path)  # type: ignore[attr-defined]
        if payload is None:
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class _ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


class McpServerTests(unittest.TestCase):
    def test_stdio_mcp_server_smoke(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        archive_path = temp_root / f"archive-{uuid4().hex}.csv"
        try:
            archive_path.write_text(
                "ticker_name,status,report_ticker,date\n"
                "TEST-MKT,finalized,TEST,2025-03-08\n",
                encoding="utf-8",
            )

            routes = {
                "/trade-api/v2/historical/cutoff": {"market_settled_ts": "2025-03-07T00:00:00Z"},
                "/trade-api/v2/markets/TEST-MKT": {
                    "market": {
                        "ticker": "TEST-MKT",
                        "event_ticker": "TEST-EVENT",
                        "series_ticker": "KXTEST",
                        "settlement_ts": "2025-03-08T00:00:00Z",
                    }
                },
                "/trade-api/v2/events/TEST-EVENT": {"event": {"series_ticker": "KXTEST"}},
                "/trade-api/v2/series/KXTEST/markets/TEST-MKT/candlesticks": {
                    "candlesticks": [
                        {
                            "end_period_ts": 1741392000,
                            "yes_bid": {
                                "close_dollars": "0.49",
                                "low_dollars": "0.48",
                                "high_dollars": "0.50",
                            },
                            "yes_ask": {
                                "close_dollars": "0.51",
                                "low_dollars": "0.50",
                                "high_dollars": "0.52",
                            },
                            "price": {"close_dollars": "0.50"},
                            "volume": 4,
                        }
                    ]
                },
            }

            with _ThreadedTCPServer(("127.0.0.1", 0), _KalshiFixtureHandler) as httpd:
                httpd.routes = routes  # type: ignore[attr-defined]
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    anyio.run(
                        self._exercise_server,
                        f"http://127.0.0.1:{httpd.server_address[1]}/trade-api/v2",
                        str(archive_path),
                        backend="asyncio",
                    )
                finally:
                    httpd.shutdown()
                    thread.join(timeout=5)
        finally:
            archive_path.unlink(missing_ok=True)

    async def _exercise_server(self, base_url: str, archive_path: str):
        server_path = Path(__file__).resolve().parents[1] / "server.py"
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_path)],
            env={
                "KALSHI_MARKET_DATA_BASE_URL": base_url,
                "KALSHI_ARCHIVE_PATH": archive_path,
            },
        )

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools = await session.list_tools()
                self.assertEqual(
                    ["download_archive", "run_backtest", "search_settled_markets", "server_info"],
                    sorted(tool.name for tool in tools.tools),
                )

                server_info = await session.call_tool("server_info", {})
                self.assertFalse(server_info.isError)
                self.assertEqual("kalshi-research-mcp", server_info.structuredContent["server"])

                search = await session.call_tool(
                    "search_settled_markets",
                    {
                        "search_term": "TEST-MKT",
                        "limit": 5,
                        "archive_path": archive_path,
                    },
                )
                self.assertFalse(search.isError)
                self.assertEqual("TEST-MKT", search.structuredContent["result"][0]["ticker"])
                self.assertEqual("TEST", search.structuredContent["result"][0]["series_ticker"])

                backtest = await session.call_tool(
                    "run_backtest",
                    {
                        "market_ticker": "TEST-MKT",
                        "series_ticker": "TEST",
                        "start_date": "2025-03-08T00:00:00Z",
                        "end_date": "2025-03-08T01:00:00Z",
                        "period_interval": 60,
                    },
                )
                self.assertFalse(backtest.isError)
                self.assertEqual("TEST-MKT", backtest.structuredContent["market_ticker"])
                self.assertEqual("KXTEST", backtest.structuredContent["series_ticker"])
                self.assertEqual("live", backtest.structuredContent["candlestick_source"])
                self.assertEqual(1, backtest.structuredContent["data_points"])


if __name__ == "__main__":
    unittest.main()
