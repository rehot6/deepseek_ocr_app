"""
配置管理模块
"""
import os
from typing import Optional


class Settings:
    """应用配置"""
    
    def __init__(self):
        # 认证配置
        self.auth_token: str = os.getenv("AUTH_TOKEN", "default_token")
        
        # Paperless 配置
        self.paperless_url: Optional[str] = os.getenv("PAPERLESS_URL")
        self.paperless_api_key: Optional[str] = os.getenv("PAPERLESS_API_KEY")
        
        # OCR 后端配置
        self.backend_ocr_url: str = os.getenv("BACKEND_OCR_URL", "http://localhost:8000")
        
        # 日志配置
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        
        # 字体配置
        self.font_file: str = os.getenv("FONT_FILE", "fonts/NotoSansCJK-Regular.ttc")
        
        # CSRF 配置
        self.csrf_token_url: str = os.getenv("CSRF_TOKEN_URL", "/api/documents/post_document/")


# 全局配置实例
settings = Settings()
