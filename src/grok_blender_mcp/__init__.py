__version__ = "0.2.0"
from .server import mcp, main
from .connection import get_blender_connection
__all__ = ["mcp", "main", "get_blender_connection", "__version__"]
