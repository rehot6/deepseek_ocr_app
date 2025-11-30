"""
自定义字体配置
"""
import os
from config import settings


class CustomFontConfig:
    """自定义字体配置"""
    
    def __init__(self, font_name="NotoSansCJK", encoding="Identity-H", font_type="Type0", font_file=None):
        self.font_name = font_name
        self.encoding = encoding
        self.font_type = font_type
        self.font_file = font_file or settings.font_file  # 使用配置中的字体文件路径
    
    def get_font_config(self):
        """获取字体配置"""
        return {
            "font_name": self.font_name,
            "encoding": self.encoding,
            "font_type": self.font_type,
            "font_file": self.font_file
        }
    
    def validate_font_file(self) -> bool:
        """
        验证字体文件是否存在
        
        Returns:
            bool: 字体文件是否存在
        """
        return os.path.exists(self.font_file)
