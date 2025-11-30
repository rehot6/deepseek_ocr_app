"""
PDF OCR 代理服务主应用
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import settings
from routers.pdf_router import router as pdf_router

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pdf_ocr_proxy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("PDF OCR代理服务启动中...")
    logger.info(f"日志级别: {settings.log_level}")
    
    # 检查字体文件
    from models.custom_font_config import CustomFontConfig
    font_config = CustomFontConfig()
    if font_config.validate_font_file():
        logger.info(f"字体文件验证成功: {font_config.font_file}")
    else:
        logger.warning(f"字体文件不存在: {font_config.font_file}")
    
    # 检查Paperless连接
    from clients.paperless_client import PaperlessClient
    paperless_client = PaperlessClient()
    if paperless_client.test_connection():
        logger.info("Paperless连接测试成功")
    else:
        logger.warning("Paperless连接测试失败或配置不完整")
    
    logger.info("PDF OCR代理服务启动完成 🚀")
    
    yield  # 应用运行期间
    
    # 关闭时执行
    logger.info("PDF OCR代理服务正在关闭...")


# FastAPI应用
app = FastAPI(
    title="PDF OCR代理服务",
    description="智能PDF OCR代理服务 - 自动检测文本并嵌入OCR结果",
    version="1.0.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(pdf_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )
