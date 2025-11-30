"""
PDF文本检测器
用于判断PDF是否已经包含有意义的文本
"""
import fitz  # PyMuPDF
import logging

logger = logging.getLogger("pdf_ocr_proxy")


class PDFTextDetector:
    """PDF文本检测器，用于判断PDF是否已经包含有意义的文本"""
    
    def __init__(self):
        self.min_meaningful_chars = 10  # 最少有意义的字符数
        self.min_chinese_chars = 5      # 最少中文字符数
        self.min_word_count = 3         # 最少单词数
    
    def has_meaningful_text(self, pdf_path: str) -> bool:
        """
        检测PDF是否包含有意义的文本
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            bool: 如果包含有意义的文本返回True，否则返回False
        """
        try:
            doc = fitz.open(pdf_path)
            total_chars = 0
            total_words = 0
            chinese_chars = 0
            
            for page in doc:
                text = page.get_text()
                if text.strip():
                    total_chars += len(text)
                    total_words += len(text.split())
                    
                    # 统计中文字符
                    for char in text:
                        if '\u4e00' <= char <= '\u9fff':
                            chinese_chars += 1
            
            doc.close()
            
            # 判断标准：
            # 1. 总字符数足够多
            # 2. 或者有足够的中文字符
            # 3. 或者有足够的单词数
            has_text = (
                total_chars >= self.min_meaningful_chars or
                chinese_chars >= self.min_chinese_chars or
                total_words >= self.min_word_count
            )
            
            logger.info(f"PDF文本检测结果 - 总字符数: {total_chars}, 中文字符数: {chinese_chars}, 单词数: {total_words}, 有意义的文本: {'是' if has_text else '否'}")
            
            return has_text
            
        except Exception as e:
            logger.error(f"PDF文本检测失败: {e}")
            return False
