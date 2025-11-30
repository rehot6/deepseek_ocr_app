"""
文件工具函数
"""
import os
import tempfile
import logging
from typing import Optional

logger = logging.getLogger("pdf_ocr_proxy")


def create_temp_file(suffix: str = ".pdf") -> str:
    """
    创建临时文件
    
    Args:
        suffix: 文件后缀
        
    Returns:
        str: 临时文件路径
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    return temp_file.name


def cleanup_temp_files(*file_paths: str) -> None:
    """
    清理临时文件
    
    Args:
        *file_paths: 要清理的文件路径列表
    """
    for file_path in file_paths:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"清理临时文件: {file_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败 {file_path}: {e}")


def ensure_directory_exists(directory: str) -> None:
    """
    确保目录存在
    
    Args:
        directory: 目录路径
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"创建目录: {directory}")


def get_file_size(file_path: str) -> Optional[int]:
    """
    获取文件大小
    
    Args:
        file_path: 文件路径
        
    Returns:
        Optional[int]: 文件大小（字节），如果文件不存在返回None
    """
    try:
        return os.path.getsize(file_path)
    except OSError:
        return None
