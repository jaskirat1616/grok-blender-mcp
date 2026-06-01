"""
Grok Blender MCP Server — Full implementation.

High-level safe tools + guarded code execution + real vision feedback (screenshots as images).
Optimized for Grok's strengths: vision, iterative reasoning, excellent Python understanding.
"""

from __future__ import annotations
import base64
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastmcp import FastMCP, Context
from mcp.types import ImageContent

from .connection import get_blender_connection, reset_connection, DEFAULT_HOST, DEFAULT_PORT

import sys
logging.basicConfig(
    level=logging.WARNING,  # Only warnings+ by default to keep stdio clean
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("grok-blender-mcp")
logger.setLevel(logging.INFO)  # Our own logs can be INFO

BLENDER_HOST = os.getenv("BLENDER_HOST", DEFAULT_HOST)
BLENDER_PORT = int(os.getenv("BLENDER_PORT", str(DEFAULT_PORT)))

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    logger.info("Grok Blender MCP starting...")
    try:
        conn = get_blender_connection(BLENDER_HOST, BLENDER_PORT)
        logger.info(f"Blender connection: {'ready' if conn.connected else 'will connect on first use'}")
    except Exception as e:
        logger.warning(f"Initial Blender connect failed (normal if Blender not running): {e}")
    yield {"host": BLENDER_HOST, "port": BLENDER_PORT}
    reset_connection()
    logger.info("Grok Blender MCP shutdown complete.")

mcp = FastMCP("GrokBlenderMCP", lifespan=lifespan)

# Suppress FastMCP banner for clean stdio (important for MCP protocol)
try:
    import fastmcp
    if hasattr(fastmcp, "settings"):
        fastmcp.settings.show_banner = False
except Exception:
    pass


# =============================================================================
# Core Tools
# =============================================================================

@mcp.tool()
async def ping(ctx: Context) -> str:
    """Health check. Returns Blender connection status and basic scene info."""
    try:
        b = get_blender_connection(BLENDER_HOST, BLENDER_PORT)
        res = b.send_command("ping")
        scene = b.send_command("get_scene_info")
        return f"✅ Connected to Blender {res.get('blender_version', '?')} on {BLENDER_HOST}:{BLENDER_PORT}\nScene: {scene.get('name')} | Objects: {scene.get('object_count')}"
    except Exception as e:
        return f"❌ Not connected: {e}\n\nStart Blender → N-panel → Grok Blender MCP tab → Connect to Grok"

@mcp.tool()
async def get_scene_info(ctx: Context, limit: int = 10) -> str:
    """Get a compact summary of the current scene (objects, counts, etc.)."""
    try:
        b = get_blender_connection()
        res = b.send_command("get_scene_info")
        objs = res.get("objects", [])[:limit]
        return json.dumps({
            "scene": res.get("name"),
            "objects": res.get("object_count"),
            "materials": res.get("materials_count"),
            "sample": objs
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
async def get_object(ctx: Context, name: str) -> str:
    """Detailed info for one object (location, rotation, scale, materials, mesh stats)."""
    try:
        b = get_blender_connection()
        return json.dumps(b.send_command("get_object_info", {"name": name}), indent=2)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
async def take_screenshot(ctx: Context, max_size: int = 1024) -> ImageContent:
    """
    Capture the active 3D viewport and return it as an image.
    This is the most important tool for vision-based iteration with Grok.
    """
    try:
        b = get_blender_connection()
        res = b.send_command("get_viewport_screenshot", {"max_size": max_size, "format": "png"})
        if not res.get("success"):
            raise Exception(res.get("error", "Screenshot failed"))
        data = base64.b64decode(res["data_base64"])
        return ImageContent(type="image", data=base64.b64encode(data).decode(), mimeType="image/png")
    except Exception as e:
        raise Exception(f"Screenshot failed: {e}")

# =============================================================================
# High-Level Safe Modeling Tools (the ones Grok should prefer)
# =============================================================================

@mcp.tool()
async def create_primitive(
    ctx: Context,
    shape: str = "cube",
    location: list[float] = None,
    scale: list[float] = None,
    name: Optional[str] = None
) -> str:
    """
    Create a primitive (cube, sphere, cylinder, plane, cone, torus).
    Always uses real-world scale. Returns the created object name.
    """
    loc = location or [0, 0, 0]
    sc = scale or [1, 1, 1]
    try:
        b = get_blender_connection()
        res = b.send_command("create_primitive", {
            "shape": shape.lower(),
            "location": loc,
            "scale": sc,
            "name": name
        })
        return f"Created {shape} '{res.get('name')}' at {loc} scale {sc}"
    except Exception as e:
        return f"Failed: {e}"

@mcp.tool()
async def transform_object(
    ctx: Context,
    name: str,
    location: Optional[list[float]] = None,
    rotation: Optional[list[float]] = None,
    scale: Optional[list[float]] = None
) -> str:
    """Move, rotate or scale an existing object. Only supply the values you want to change."""
    try:
        b = get_blender_connection()
        params = {"name": name}
        if location is not None: params["location"] = location
        if rotation is not None: params["rotation"] = rotation
        if scale is not None: params["scale"] = scale
        b.send_command("transform_object", params)
        return f"Transformed '{name}'"
    except Exception as e:
        return f"Failed: {e}"

@mcp.tool()
async def set_material(
    ctx: Context,
    object_name: str,
    color: list[float] = None,
    metallic: float = 0.0,
    roughness: float = 0.5,
    name: Optional[str] = None
) -> str:
    """Apply a simple PBR material to an object. Color as [R,G,B] 0-1."""
    col = color or [0.8, 0.8, 0.8]
    try:
        b = get_blender_connection()
        res = b.send_command("set_material", {
            "object_name": object_name,
            "color": col,
            "metallic": metallic,
            "roughness": roughness,
            "material_name": name
        })
        return f"Applied material to '{object_name}': {res}"
    except Exception as e:
        return f"Failed: {e}"

@mcp.tool()
async def add_light(
    ctx: Context,
    light_type: str = "sun",
    location: list[float] = None,
    energy: float = 1.0,
    color: list[float] = None
) -> str:
    """Add a light (sun, point, area, spot)."""
    loc = location or [0, 0, 5]
    col = color or [1, 1, 1]
    try:
        b = get_blender_connection()
        res = b.send_command("add_light", {
            "type": light_type.lower(),
            "location": loc,
            "energy": energy,
            "color": col
        })
        return f"Added {light_type} light: {res.get('name')}"
    except Exception as e:
        return f"Failed: {e}"

@mcp.tool()
async def setup_camera(
    ctx: Context,
    location: list[float] = None,
    look_at: list[float] = None,
    focal_length: float = 50.0
) -> str:
    """Position the camera and point it at a target."""
    loc = location or [0, -10, 5]
    target = look_at or [0, 0, 0]
    try:
        b = get_blender_connection()
        res = b.send_command("setup_camera", {
            "location": loc,
            "look_at": target,
            "focal_length": focal_length
        })
        return f"Camera positioned: {res}"
    except Exception as e:
        return f"Failed: {e}"

@mcp.tool()
async def undo(ctx: Context, steps: int = 1) -> str:
    """Undo recent actions (highly recommended after any mistake)."""
    try:
        b = get_blender_connection()
        b.send_command("undo", {"steps": max(1, min(steps, 50))})
        return f"Undid {steps} step(s)"
    except Exception as e:
        return f"Undo failed: {e}"

# =============================================================================
# Power Tool (use with extreme caution)
# =============================================================================

@mcp.tool()
async def execute_code(ctx: Context, code: str, dry_run: bool = True) -> str:
    """
    Execute raw Python in Blender. 
    STRONGLY prefer the high-level tools above. Only use this when necessary.
    Always start with dry_run=True.
    """
    if dry_run:
        dangerous = any(x in code.lower() for x in ["os.", "subprocess", "open(", "write(", "sys.exit", "__import__"])
        if dangerous:
            return "⚠️ DRY RUN: Potentially dangerous operations detected (file I/O, subprocess, etc). Review carefully before setting dry_run=False."
        return f"✅ DRY RUN OK (basic safety scan passed).\n\n{code[:600]}..."
    try:
        b = get_blender_connection()
        res = b.send_command("execute_code", {"code": code})
        return f"Executed.\n{res.get('stdout', '')[:1500]}"
    except Exception as e:
        return f"Execution error: {e}"

# =============================================================================
# Grok-Optimized Resources & Prompts
# =============================================================================

@mcp.resource("grok://strategy/3d-modeling")
def modeling_strategy() -> str:
    return """# Grok + Blender MCP — Best Practices (v0.2)

## Golden Rules
1. **See first** — Always call take_screenshot() after significant changes. You can literally see the result.
2. **Small steps** — One logical change per turn. Verify with screenshot + get_object().
3. **High-level first** — create_primitive, transform_object, set_material, add_light, setup_camera are safe and reliable.
4. **Undo is free** — Use the undo tool liberally.
5. **Safe Mode is your friend** — The addon starts restrictive. Only escalate to execute_code when truly needed, and always dry_run first.

## Recommended Workflow
Inspect (get_scene_info + screenshot) → Plan one atomic change → Execute high-level tool → Screenshot + verify → Repeat.

## Using Your Own Image Generation
Generate reference images with your Flux/Aurora tool, save them, then describe them or use them as modeling guides inside Blender.

Save your .blend often. This tool gives you real power — use it responsibly.
"""

@mcp.prompt()
def iterative_blender_session() -> str:
    return """You are an expert 3D artist working inside Blender through the Grok Blender MCP tools.

Goal: {goal}

Process:
- Start by inspecting the scene and taking a screenshot.
- Break the task into tiny verifiable steps.
- After every change, take a screenshot and reason about what you see (scale, position, lighting, materials).
- Prefer high-level tools (create_primitive, transform, set_material, etc.).
- Use undo immediately if something looks wrong.
- Only use execute_code when high-level tools are insufficient, and always propose it with dry_run=True first.

Begin.
"""

def main():
    mcp.run()

if __name__ == "__main__":
    main()
