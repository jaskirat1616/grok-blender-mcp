#!/bin/bash
set -e

echo "Setting up Grok Blender MCP..."
cd "$(dirname "$0")"

uv venv --python 3.10
source .venv/bin/activate
uv pip install -e .

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. In Blender: Edit → Preferences → Add-ons → Install → select blender-addon/addon.py"
echo "2. Press N in the 3D View → Grok Blender MCP tab → Click 'Connect to Grok'"
echo "3. Add the MCP server to Grok (see README.md for the recommended command)"
echo ""
echo "Then restart Grok and start building!"
