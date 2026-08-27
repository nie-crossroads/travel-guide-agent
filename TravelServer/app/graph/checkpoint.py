from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.config import settings


def open_checkpointer():
    """异步 SQLite 检查点：与 FastAPI lifespan 配套，进程退出时关闭连接。"""
    return AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_path))
