"""项目入口：uvicorn main:app 或 python main.py。"""
import uvicorn

from app.core.config import settings
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
