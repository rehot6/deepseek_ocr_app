"""
字体分析器
用于检测PDF中的字体信息
"""
import fitz  # PyMuPDF
import logging
from typing import Dict, Any

logger = logging.getLogger("pdf_ocr_proxy")


class FontAnalyzer:
    """字体分析器，用于检测PDF中的字体信息"""
    
    def analyze_fonts(self, pdf_path: str) -> Dict[str, Any]:
        """
        分析PDF中的字体信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Dict: 字体分析结果
        """
        try:
            doc = fitz.open(pdf_path)
            font_info = {
                "fonts": [],
                "recommended_font": "china-ss",  # 默认字体
                "has_cid_fonts": False,
                "has_identity_h": False,
                "font_details": []
            }
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                fonts = page.get_fonts()
                
                for font in fonts:
                    font_xref = font[0] if len(font) > 0 else None
                    font_ext = font[1] if len(font) > 1 else "Unknown"
                    font_type = font[2] if len(font) > 2 else "Unknown"
                    font_name = font[3] if len(font) > 3 else "Unknown"
                    font_encoding = font[4] if len(font) > 4 else "Unknown"
                    font_subtype = font[5] if len(font) > 5 else "Unknown"
                    
                    font_data = {
                        "xref": font_xref,
                        "extension": font_ext,
                        "type": font_type,
                        "name": font_name,
                        "encoding": font_encoding,
                        "subtype": font_subtype,
                        "page": page_num + 1
                    }
                    
                    # 检查是否是CID字体
                    if "CIDFont" in font_name or font_type == "Type0":
                        font_info["has_cid_fonts"] = True
                    
                    # 检查是否是Identity-H编码
                    if font_encoding == "Identity-H":
                        font_info["has_identity_h"] = True
                    
                    # 尝试提取字体详细信息
                    try:
                        if font_xref:
                            font_buffer = doc.extract_font(font_xref)
                            if font_buffer:
                                font_data["has_buffer"] = True
                                font_data["buffer_size"] = len(font_buffer)
                            else:
                                font_data["has_buffer"] = False
                        else:
                            font_data["has_buffer"] = False
                    except:
                        font_data["has_buffer"] = False
                    
                    # 添加到字体列表（去重）
                    if font_data not in font_info["fonts"]:
                        font_info["fonts"].append(font_data)
            
            # 根据检测到的字体推荐合适的字体
            if font_info["has_cid_fonts"] or font_info["has_identity_h"]:
                # 对于CID字体和Identity-H编码，使用支持中文的字体
                font_info["recommended_font"] = "china-ss"
            elif any("Times" in font["name"] for font in font_info["fonts"]):
                font_info["recommended_font"] = "Times-Roman"
            elif any("Helvetica" in font["name"] for font in font_info["fonts"]):
                font_info["recommended_font"] = "Helvetica"
            elif any("Arial" in font["name"] for font in font_info["fonts"]):
                font_info["recommended_font"] = "Helvetica"  # Arial的替代
            else:
                font_info["recommended_font"] = "china-ss"  # 默认使用中文字体
            
            doc.close()
            
            logger.info(f"字体分析结果 - 检测到 {len(font_info['fonts'])} 种字体, 推荐字体: {font_info['recommended_font']}")
            
            return font_info
            
        except Exception as e:
            logger.error(f"字体分析失败: {e}")
            return {
                "fonts": [],
                "recommended_font": "china-ss",
                "has_cid_fonts": False,
                "has_identity_h": False,
                "font_details": []
            }
