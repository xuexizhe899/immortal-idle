"""本地开发入口：在 backend 目录执行 `python app.py` 启动服务。"""

from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        # 只监听源码与配置，避免把 .venv、data 目录也纳入热重载
        reload_dirs=[
            str(BACKEND_DIR / "app"),
            str(BACKEND_DIR.parent / "config"),
        ],
    )
