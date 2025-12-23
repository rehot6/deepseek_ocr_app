#!/usr/bin/env python3
"""
测试超时设置的脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from process_pdfs import PDFBatchProcessor
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_timeout")

def test_ocr_timeout():
    """测试OCR超时设置"""
    
    # 使用与之前相同的参数
    base_url = "http://localhost:8001"
    auth_token = "U6drUduBRoM1vGga7Di2cVse7jiURNsDZUGGDcEyofTOO7F66KbBbqSeILfTfFg3"
    
    # 创建处理器
    processor = PDFBatchProcessor(base_url, auth_token)
    
    # 测试_monitor_task函数的超时设置
    print("测试_monitor_task函数的超时设置...")
    print(f"默认max_wait: 3600秒 ({3600//60}分钟)")
    
    # 检查OCR嵌入器的超时设置
    from proxy.services.ocr_embedder import OCRTextEmbedder
    embedder = OCRTextEmbedder()
    
    # 模拟一个PDF文件
    test_pdf = "renamed_pdfs/GBT+28448-2019.pdf"
    if os.path.exists(test_pdf):
        print(f"测试PDF文件: {test_pdf}")
        
        # 获取PDF页数
        import fitz
        try:
            with fitz.open(test_pdf) as doc:
                page_count = len(doc)
                print(f"PDF页数: {page_count}")
                
                # 计算动态超时
