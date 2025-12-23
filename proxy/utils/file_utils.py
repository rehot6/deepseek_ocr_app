"""
文件工具函数
"""
import os
import tempfile
import shutil
import logging
from datetime import datetime
from typing import Optional

from config import settings

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


def save_to_local_directory(source_file: str, original_filename: str = None) -> Optional[str]:
    """
    将文件保存到本地目录
    
    Args:
        source_file: 源文件路径
        original_filename: 原始文件名（可选）
        
    Returns:
        Optional[str]: 保存后的文件路径，如果保存失败返回None
    """
    if not settings.local_save_enabled or not settings.local_save_dir:
        logger.debug("本地保存功能未启用或未配置保存目录")
        return None
    
    try:
        # 确保目录存在
        ensure_directory_exists(settings.local_save_dir)
        
        # 生成目标文件名
        if original_filename:
            # 使用原始文件名，添加时间戳避免冲突
            base_name = os.path.splitext(original_filename)[0]
            ext = os.path.splitext(original_filename)[1] or ".pdf"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_filename = f"{base_name}_{timestamp}{ext}"
        else:
            # 使用源文件名
            source_basename = os.path.basename(source_file)
            base_name = os.path.splitext(source_basename)[0]
            ext = os.path.splitext(source_basename)[1] or ".pdf"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_filename = f"{base_name}_{timestamp}{ext}"
        
        # 完整目标路径
        target_path = os.path.join(settings.local_save_dir, target_filename)
        
        # 复制文件
        shutil.copy2(source_file, target_path)
        
        logger.info(f"文件已保存到本地目录: {target_path}")
        return target_path
        
    except Exception as e:
        logger.error(f"保存文件到本地目录失败: {e}")
        return None
