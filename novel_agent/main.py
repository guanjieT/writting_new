from __future__ import annotations

import uvicorn

from .config import load_config
from .api.app import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    config = load_config()
    uvicorn.run(create_app(config), host=config.server_host, port=config.server_port, reload=False)
