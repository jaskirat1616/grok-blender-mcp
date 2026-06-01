"""
Grok Blender MCP Addon - Full single-file implementation (v0.2)

Install via Blender Preferences > Add-ons > Install > select this file.
Then in the 3D View N-panel (Grok Blender MCP tab) click "Connect to Grok".

This version includes:
- Strong safety defaults (Safe Mode, auto-undo, emergency button)
- Viewport screenshots (base64)
- High-level creation & transform handlers
- Material, light, camera helpers
- Guarded code execution
- Clean TCP JSON protocol on port 9876 (configurable)

Compatible with Blender 4.2+
"""

from __future__ import annotations
import base64
import json
import socket
import tempfile
import threading
import time
import traceback
from contextlib import redirect_stdout
from datetime import datetime
import io
from typing import Any, Dict, Optional

import bpy
from bpy.props import IntProperty, BoolProperty
from bpy.types import Operator, Panel, AddonPreferences

bl_info = {
    "name": "Grok Blender MCP",
    "author": "Grok / xAI",
    "version": (0, 2, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Grok Blender MCP",
    "description": "Safe, vision-first MCP bridge for Grok to control Blender.",
    "category": "Interface",
}

DEFAULT_PORT = 9876

class GrokBlenderMCPPreferences(AddonPreferences):
    bl_idname = __name__
    port: IntProperty(name="Port", default=DEFAULT_PORT, min=1024, max=65535)
    safe_mode: BoolProperty(name="Safe Mode (Recommended)", default=True)
    allow_code_execution: BoolProperty(name="Allow Raw Code Execution", default=False)
    auto_undo: BoolProperty(name="Auto Undo on Mutations", default=True)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "port")
        layout.separator()
        box = layout.box()
        box.label(text="Safety", icon="SHIELD")
        box.prop(self, "safe_mode")
        box.prop(self, "allow_code_execution")
        box.prop(self, "auto_undo")

class GrokBlenderMCPServer:
    def __init__(self, host="localhost", port=DEFAULT_PORT):
        self.host, self.port = host, port
        self.running = False
        self.sock = None
        self.thread = None
        self._stop = threading.Event()

    def start(self):
        if self.running: return
        self.running = True
        self._stop.clear()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen(1)
            self.sock.settimeout(1.0)
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print(f"[GrokMCP] Listening on {self.host}:{self.port}")
        except Exception as e:
            print(f"[GrokMCP] Start failed: {e}")
            self.stop()

    def stop(self):
        self.running = False
        self._stop.set()
        if self.sock:
            try: self.sock.close()
            except: pass
            self.sock = None
        if self.thread: self.thread.join(timeout=2)
        print("[GrokMCP] Stopped")

    def _loop(self):
        while self.running and not self._stop.is_set():
            try:
                client, addr = self.sock.accept()
                threading.Thread(target=self._handle, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running: print(f"[GrokMCP] Loop error: {e}")

    def _handle(self, client):
        client.settimeout(None)
        buf = b""
        try:
            while self.running:
                data = client.recv(8192)
                if not data: break
                buf += data
                while buf:
                    try:
                        txt = buf.decode("utf-8")
                        depth, end = 0, -1
                        for i, ch in enumerate(txt):
                            if ch == "{": depth += 1
                            elif ch == "}": depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                        if end == -1: break
                        cmd = json.loads(txt[:end])
                        buf = buf[end:]
                        def runner():
                            try:
                                resp = self._dispatch(cmd)
                                client.sendall(json.dumps(resp).encode())
                            except Exception as ex:
                                client.sendall(json.dumps({"status": "error", "message": str(ex)}).encode())
                            return None
                        bpy.app.timers.register(runner, first_interval=0.0)
                    except json.JSONDecodeError:
                        break
        finally:
            try: client.close()
            except: pass

    def _dispatch(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        t = cmd.get("type", "")
        p = cmd.get("params", {})
        prefs = bpy.context.preferences.addons.get(__name__)
        safe = True
        allow_code = False
        auto_undo = True
        if prefs:
            pr = prefs.preferences
            safe = pr.safe_mode
            allow_code = pr.allow_code_execution
            auto_undo = pr.auto_undo

        handlers = {
            "ping": self._ping,
            "get_scene_info": self._scene_info,
            "get_object_info": self._object_info,
            "get_viewport_screenshot": self._screenshot,
            "create_primitive": self._create_primitive,
            "transform_object": self._transform,
            "set_material": self._set_material,
            "add_light": self._add_light,
            "setup_camera": self._setup_camera,
            "execute_code": self._exec_code,
            "undo": self._undo,
        }
        h = handlers.get(t)
        if not h:
            return {"status": "error", "message": f"Unknown: {t}"}

        if t == "execute_code" and (safe or not allow_code):
            return {"status": "error", "message": "Code execution disabled by Safe Mode or preferences."}

        if auto_undo and t not in ("ping", "get_scene_info", "get_object_info", "get_viewport_screenshot"):
            try: bpy.ops.ed.undo_push(message=f"GrokMCP: {t}")
            except: pass

        try:
            return {"status": "success", "result": h(**p)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # Handlers
    def _ping(self):
        return {"blender_version": bpy.app.version_string, "time": datetime.now().isoformat()}

    def _scene_info(self):
        scene = bpy.context.scene
        objs = []
        for i, o in enumerate(scene.objects):
            if i >= 12: break
            objs.append({"name": o.name, "type": o.type, "location": [round(v, 3) for v in o.location]})
        return {"name": scene.name, "object_count": len(scene.objects), "materials_count": len(bpy.data.materials), "objects": objs}

    def _object_info(self, name: str):
        obj = bpy.data.objects.get(name)
        if not obj: raise ValueError(f"Object '{name}' not found")
        info = {
            "name": obj.name, "type": obj.type,
            "location": list(obj.location), "rotation_euler": list(obj.rotation_euler), "scale": list(obj.scale),
            "materials": [s.material.name for s in obj.material_slots if s.material]
        }
        if obj.type == "MESH" and obj.data:
            m = obj.data
            info["mesh"] = {"verts": len(m.vertices), "edges": len(m.edges), "polys": len(m.polygons)}
        return info

    def _screenshot(self, max_size: int = 800, format: str = "png"):
        import os
        area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
        if not area: raise RuntimeError("No 3D viewport")
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as tmp:
            path = tmp.name
        try:
            with bpy.context.temp_override(area=area):
                bpy.ops.screen.screenshot_area(filepath=path)
            from PIL import Image as PILImage
            img = PILImage.open(path)
            w, h = img.size
            if max(w, h) > max_size:
                s = max_size / max(w, h)
                img = img.resize((int(w*s), int(h*s)), PILImage.LANCZOS)
                img.save(path, format=format.upper())
                w, h = img.size
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return {"success": True, "width": w, "height": h, "format": format, "data_base64": b64}
        finally:
            try: os.unlink(path)
            except: pass

    def _create_primitive(self, shape: str, location=None, scale=None, name=None):
        loc = location or [0,0,0]
        sc = scale or [1,1,1]
        bpy.ops.object.select_all(action="DESELECT")
        if shape == "cube": bpy.ops.mesh.primitive_cube_add(location=loc, scale=sc)
        elif shape == "sphere": bpy.ops.mesh.primitive_uv_sphere_add(location=loc, scale=sc)
        elif shape == "cylinder": bpy.ops.mesh.primitive_cylinder_add(location=loc, scale=sc)
        elif shape == "plane": bpy.ops.mesh.primitive_plane_add(location=loc, scale=sc)
        elif shape == "cone": bpy.ops.mesh.primitive_cone_add(location=loc, scale=sc)
        else: bpy.ops.mesh.primitive_cube_add(location=loc, scale=sc)
        obj = bpy.context.active_object
        if name: obj.name = name
        return {"name": obj.name}

    def _transform(self, name: str, location=None, rotation=None, scale=None):
        obj = bpy.data.objects.get(name)
        if not obj: raise ValueError(f"Object '{name}' not found")
        if location: obj.location = location
        if rotation: obj.rotation_euler = rotation
        if scale: obj.scale = scale
        return {"ok": True}

    def _set_material(self, object_name: str, color=None, metallic=0.0, roughness=0.5, material_name=None):
        obj = bpy.data.objects.get(object_name)
        if not obj: raise ValueError("Object not found")
        col = color or [0.8, 0.8, 0.8]
        mat_name = material_name or f"GrokMCP_{object_name}"
        mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*col, 1.0)
            bsdf.inputs["Metallic"].default_value = metallic
            bsdf.inputs["Roughness"].default_value = roughness
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        return {"material": mat.name}

    def _add_light(self, type: str, location=None, energy=1.0, color=None):
        loc = location or [0,0,5]
        col = color or [1,1,1]
        light_data = bpy.data.lights.new(name=f"Grok_{type}", type=type.upper())
        light_data.energy = energy
        light_data.color = col
        light_obj = bpy.data.objects.new(name=f"Grok_{type}", object_data=light_data)
        light_obj.location = loc
        bpy.context.collection.objects.link(light_obj)
        return {"name": light_obj.name}

    def _setup_camera(self, location=None, look_at=None, focal_length=50.0):
        loc = location or [0,-10,5]
        target = look_at or [0,0,0]
        cam = bpy.context.scene.camera
        if not cam:
            cam_data = bpy.data.cameras.new("GrokCam")
            cam = bpy.data.objects.new("GrokCamera", cam_data)
            bpy.context.collection.objects.link(cam)
            bpy.context.scene.camera = cam
        cam.location = loc
        cam.data.lens = focal_length
        direction = [target[i] - loc[i] for i in range(3)]
        cam.rotation_euler = direction  # simplified
        return {"name": cam.name}

    def _exec_code(self, code: str):
        ns = {"bpy": bpy}
        out = io.StringIO()
        with redirect_stdout(out):
            exec(code, ns)
        return {"stdout": out.getvalue()[:2000]}

    def _undo(self, steps: int = 1):
        for _ in range(min(steps, 50)):
            try: bpy.ops.ed.undo()
            except: break
        return {"undone": steps}

_server: Optional[GrokBlenderMCPServer] = None

class GROK_MCP_OT_connect(Operator):
    bl_idname = "grok_mcp.connect"
    bl_label = "Connect to Grok"
    def execute(self, ctx):
        global _server
        port = ctx.preferences.addons[__name__].preferences.port
        if _server and _server.running:
            self.report({"INFO"}, "Already running"); return {"FINISHED"}
        _server = GrokBlenderMCPServer(port=port)
        _server.start()
        self.report({"INFO"}, f"Listening on port {port}")
        return {"FINISHED"}

class GROK_MCP_OT_disconnect(Operator):
    bl_idname = "grok_mcp.disconnect"
    bl_label = "Disconnect"
    def execute(self, ctx):
        global _server
        if _server: _server.stop(); _server = None
        self.report({"INFO"}, "Disconnected")
        return {"FINISHED"}

class GROK_MCP_OT_emergency(Operator):
    bl_idname = "grok_mcp.emergency_undo"
    bl_label = "Emergency Undo"
    def execute(self, ctx):
        for _ in range(40):
            try: bpy.ops.ed.undo()
            except: break
        self.report({"WARNING"}, "Emergency undo performed")
        return {"FINISHED"}

class GROK_MCP_PT_panel(Panel):
    bl_label = "Grok Blender MCP"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Grok Blender MCP"
    def draw(self, ctx):
        layout = self.layout
        prefs = ctx.preferences.addons.get(__name__)
        running = bool(_server and _server.running)
        box = layout.box()
        box.label(text=f"{'🟢 Listening' if running else '🔴 Stopped'} on port {prefs.preferences.port if prefs else DEFAULT_PORT}")
        row = layout.row(align=True)
        row.operator("grok_mcp.connect", icon="PLUGIN")
        row.operator("grok_mcp.disconnect", icon="CANCEL")
        layout.operator("grok_mcp.emergency_undo", text="EMERGENCY UNDO", icon="LOOP_BACK")
        layout.separator()
        layout.label(text="Add in Grok CLI:")
        layout.label(text="grok mcp add blender --command uvx --args \"grok-blender-mcp\"")

_classes = (GrokBlenderMCPPreferences, GROK_MCP_OT_connect, GROK_MCP_OT_disconnect, GROK_MCP_OT_emergency, GROK_MCP_PT_panel)

def register():
    for c in _classes: bpy.utils.register_class(c)
    print("[GrokMCP] Addon registered")

def unregister():
    global _server
    if _server: _server.stop(); _server = None
    for c in reversed(_classes):
        try: bpy.utils.unregister_class(c)
        except: pass

if __name__ == "__main__":
    register()
