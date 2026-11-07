"""A local, read-only MCP tool with arguments inferred from its type hints."""

from mcp.server import MCPServer

server = MCPServer("lesson_tools")


@server.tool()
def count_words(text: str) -> int:
    """Count whitespace-separated tokens in text; punctuation remains attached."""
    return len(text.split())


if __name__ == "__main__":
    server.run()
