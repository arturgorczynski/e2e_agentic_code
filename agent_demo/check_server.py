"""Exercise the actual host-configured stdio launcher from a subdirectory."""

import asyncio
import json
import tomllib
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


async def main():
    codex_config = ROOT / ".codex/config.toml"
    if codex_config.exists():
        config = tomllib.loads(codex_config.read_text())["mcp_servers"]["lesson_tools"]
    else:
        config = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["lesson_tools"]
    params = StdioServerParameters(command=config["command"], args=config["args"], cwd=ROOT / "notebooks")
    # Check both the modern protocol and the handshake used by older hosts.
    for mode in ("auto", "legacy"):
        async with Client(params, mode=mode, read_timeout_seconds=20) as client:
            tools = (await client.list_tools()).tools
            assert [tool.name for tool in tools] == ["count_words"], tools
            schema = tools[0].input_schema
            assert schema["required"] == ["text"], schema
            assert schema["properties"]["text"]["type"] == "string", schema
            for text, expected in (("small useful example", 3), ("", 0), ("one\ttwo\nthree!", 3)):
                result = await client.call_tool("count_words", {"text": text})
                assert not result.is_error, result
                assert result.structured_content == {"result": expected}, result
            invalid = await client.call_tool("count_words", {})
            assert invalid.is_error, invalid
            print(f"PASS: {mode} stdio discovery, argument schema, counts, and missing-argument rejection")


if __name__ == "__main__":
    asyncio.run(main())
