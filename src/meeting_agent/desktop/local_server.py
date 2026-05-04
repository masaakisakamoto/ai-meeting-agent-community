from __future__ import annotations
import threading, webbrowser
from pathlib import Path
from meeting_agent.desktop.bridge import DesktopBridgeConfig, create_desktop_bridge_server, make_desktop_bridge_handler

# Compatibility alias used in tests/older docs.
make_desktop_handler = make_desktop_bridge_handler

def serve_desktop_alpha(*, workspace_dir: str|Path, ui_dir: str|Path|None=None, host: str="127.0.0.1", port: int=8765, open_browser: bool=False) -> None:
    workspace=Path(workspace_dir); config=DesktopBridgeConfig(workspace=workspace, static_dir=ui_dir or workspace/"desktop_lite", host=host, port=port); server=create_desktop_bridge_server(config); url=f"http://{host}:{server.server_port}/"
    if open_browser: threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    print(f"Desktop Alpha bridge listening on {url}"); print(f"Workspace: {workspace.resolve()}")
    try: server.serve_forever()
    finally: server.server_close()
