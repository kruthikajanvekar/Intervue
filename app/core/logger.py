"""
Loguru-based logger, configured once here and imported everywhere else.
Writes to stdout (for `docker logs`) and to a rotating file under ./logs.
"""
import sys

from loguru import logger

from app.core.config import settings

logger.remove()

logger.add(
    sys.stdout,
    level="DEBUG" if settings.debug else "INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="14 days",
    level="INFO",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

__all__ = ["logger"]
