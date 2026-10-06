"""
集中式日誌配置模組
提供結構化日誌功能，統一處理所有應用程式的日誌記錄
"""
import logging
import sys
from pythonjsonlogger import json
from datetime import datetime
from typing import Any, Mapping


def setup_logging() -> None:
    """配置全域日誌系統，使用JSON格式輸出結構化日誌"""
    # 設定根日誌器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除現有處理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 建立JSON格式的日誌處理器
    json_handler = logging.StreamHandler(sys.stdout)
    formatter = json.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s %(module)s %(funcName)s %(lineno)d',
        style="%"
    )
    json_handler.setFormatter(formatter)
    logger.addHandler(json_handler)

    # 也保留一個給開發者友好的控制台輸出（可選）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    # 只添加一次，避免重複輸出
    # logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    取得指定名稱的日誌器，確保所有日誌器都使用相同配置
    
    使用方式:
        logger = get_logger(__name__)
        logger.info("操作成功", extra={"customer_id": 123, "amount": 100})
        logger.error("操作失敗", exc_info=True, extra={"error_context": {...}})
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    context: Mapping[str, Any] | None = None,
    exc_info: bool = False
) -> None:
    """
    帶有上下文資訊的日誌記錄方法
    
    參數:
        logger: 日誌器實例
        level: 日誌級別 (logging.INFO, logging.ERROR等)
        message: 日誌訊息
        context: 要附加的上下文資訊字典
        exc_info: 是否記錄例外資訊
    """
    extra = context.copy() if context else {}
    extra['timestamp'] = datetime.utcnow().isoformat()
    
    logger.log(level, message, extra=extra, exc_info=exc_info)