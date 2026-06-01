# Grok Blender MCP

A **Grok-first** Model Context Protocol (MCP) server that gives Grok native control over Blender.

Describe what you want in natural language and watch Grok build, modify, and iterate on 3D scenes directly in Blender - with real vision feedback via viewport screenshots.

## Features

- **High-level safe tools** - Create primitives, transform objects, apply materials, add lights, set up cameras, etc.
- **Real vision feedback** - `take_screenshot` returns actual viewport images so Grok can see what it just created.
- **Strong safety defaults** - Safe Mode enabled by default, automatic undo on every mutation, emergency undo button in Blender.
- **Guarded code execution** - Powerful escape hatch with dry-run mode and basic safety scanning.
- **Grok-optimized** - Includes curated prompting strategies and workflows designed for Grok's strengths.

## Prerequisites

- Blender 4.2+
- [Grok CLI](https://x.ai) (or any compatible MCP client)
- Python 3.10+
- `uv` (recommended) or pip

## Installation

### 1. Install the Blender Addon

1. Download or clone this repository.
2. In Blender: **Edit → Preferences → Add-ons → Install...**
3. Select `blender-addon/addon.py`
4. Enable **"Grok Blender MCP"**

### 2. Connect the Addon

1. In the 3D Viewport, press **N** to open the sidebar.
2. Go to the **Grok Blender MCP** tab.
3. Click **"Connect to Grok"** (it will start listening on port 9876 by default).

### 3. Add the MCP Server to Grok

```bash
# Recommended: Remove any previous broken entries first
grok mcp remove blender 2>/dev/null || true

# Add using the local installation
grok mcp add blender \
  --command python \
  --args -- -m grok_blender_mcp.server \
  --env "PYTHONPATH=/absolute/path/to/grok-blender-mcp/src"
```

> **Tip**: Replace `/absolute/path/to/grok-blender-mcp` with the actual path on your machine.

After adding, **fully restart** the Grok CLI/TUI, then verify with:

```bash
grok mcp list
```

Or inside Grok: `/mcps`

## Usage

Once connected, you can talk to Grok naturally:

- "Take a screenshot of the current viewport"
- "Create a red metallic cube on a gray plane with dramatic lighting"
- "Build a simple low-poly chair"
- "Make the sphere look like brushed steel and show me the result"

Grok will use the available tools, take screenshots when helpful, and iterate with you.

## Project Structure

```
grok-blender-mcp/
├── blender-addon/
│   └── addon.py              # Single-file Blender addon (easy to install)
├── src/grok_blender_mcp/
│   ├── server.py             # Main MCP server (FastMCP)
│   └── connection.py         # Robust TCP client to Blender
├── docs/
│   └── SAFETY.md
├── pyproject.toml
└── README.md
```

## Safety

This tool gives an AI significant control over Blender. We built it with strong safeguards:

- Safe Mode (default on)
- Automatic undo on mutations
- Emergency undo button inside Blender
- Dry-run mode for raw code execution

See [docs/SAFETY.md](docs/SAFETY.md) for details.

## Development

```bash
cd grok-blender-mcp
uv venv
source .venv/bin/activate
uv pip install -e .
uv run grok-blender-mcp
```

## Architecture

```
Grok (CLI/TUI) 
   ↔ MCP (stdio)
      ↔ Python Server (FastMCP)
         ↔ TCP Socket (9876)
            ↔ Blender Addon (bpy)
```

## Troubleshooting

**"Blender MCP unavailable" in Grok but Blender says it's listening**

- Make sure you restarted Grok completely after adding the server.
- Test the server manually:
  ```bash
  cd /path/to/grok-blender-mcp
  source .venv/bin/activate
  python -m grok_blender_mcp.server
  ```
- Check that the `PYTHONPATH` in your MCP config points to the `src` folder.

**Connection refused**

- Confirm the addon is running and shows "Listening on port 9876".
- Try a different port by setting `BLENDER_PORT` in your environment when adding the MCP.

## License

MIT

---

Built as a custom integration to give Grok first-class 3D modeling capabilities inside Blender.

## Links

- **Repository**: https://github.com/jaskirat1616/grok-blender-mcp
- **Issues**: https://github.com/jaskirat1616/grok-blender-mcp/issues

---

*Built to give Grok powerful, safe, and vision-aware control over Blender.*
