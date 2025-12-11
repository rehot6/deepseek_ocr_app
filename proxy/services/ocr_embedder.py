"""
OCR文本嵌入器
用于将OCR结果嵌入到PDF中
"""
import os
import requests
import fitz  # PyMuPDF
import logging
from typing import List, Dict, Any
from fastapi import HTTPException

from config import settings
from models.font_analyzer import FontAnalyzer
from models.custom_font_config import CustomFontConfig

logger = logging.getLogger("pdf_ocr_proxy")


class OCRTextEmbedder:
    """OCR文本嵌入器，用于将OCR结果嵌入到PDF中"""
    
    def __init__(self, custom_font_config=None):
        self.backend_url = settings.backend_ocr_url
        self.font_analyzer = FontAnalyzer()
        self.custom_font_config = custom_font_config or CustomFontConfig()
    
    def remove_text_preserve_appearance(self, input_pdf: str, output_pdf: str, dpi: int = 300) -> str:
        """
        通过将每页渲染为图像来彻底删除文本层
        保留原始视觉效果，但会损失矢量信息
        
        Args:
            input_pdf: 输入PDF路径
            output_pdf: 输出PDF路径
            dpi: 图像分辨率（默认300）
            
        Returns:
            str: 输出PDF路径
        """
        try:
            logger.info(f"删除文本层，保留图像层，DPI={dpi}...")
            
            doc = fitz.open(input_pdf)
            
            # 创建一个新的空PDF
            new_doc = fitz.open()
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # 将页面渲染为高分辨率图像
                matrix = fitz.Matrix(dpi/72, dpi/72)  # 提高DPI保持清晰度
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                
                # 将Pixmap转换为图像数据
                img_data = pix.tobytes("png")
                
                # 创建新的PDF页面（与原始页面相同尺寸）
                new_page = new_doc.new_page(width=page.rect.width, 
                                           height=page.rect.height)
                
                # 在相同位置插入图像
                rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
                new_page.insert_image(rect, stream=img_data)
                
                logger.debug(f"页面 {page_num+1} 已转换为图像")
            
            # 保存新PDF
            new_doc.save(output_pdf, deflate=True)
            new_doc.close()
            doc.close()
            
            logger.info(f"文本层已删除，生成纯图像PDF: {output_pdf}")
            return output_pdf
            
        except Exception as e:
            logger.error(f"删除文本层失败: {e}")
            raise HTTPException(status_code=500, detail=f"删除文本层失败: {str(e)}")
    
    def perform_ocr(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        调用后端OCR服务处理PDF
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            List[Dict]: OCR结果数据
        """
        try:
            logger.info("调用后端OCR服务...")
            
            # 读取PDF文件
            with open(pdf_path, 'rb') as f:
                files = {'pdf_file': ('input.pdf', f, 'application/pdf')}
                data = {
                    'mode': 'plain_ocr',
                    'output_format': 'json',
                    'dpi': 144
                }
                
                # 发送请求到后端OCR服务
                response = requests.post(
                    f"{self.backend_url}/api/process-pdf",
                    files=files,
                    data=data,
                    timeout=300  # 5分钟超时
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"OCR处理完成，共 {result.get('total_pages', 0)} 页")
                    
                    pages = result.get('pages', [])
                    logger.debug(f"OCR返回的页面数据: {len(pages)} 页")
                    
                    return pages
                else:
                    logger.error(f"OCR服务返回错误: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=500, detail=f"OCR服务错误: {response.text}")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"连接OCR服务失败: {e}")
            raise HTTPException(status_code=503, detail="OCR服务不可用")
        except Exception as e:
            logger.error(f"OCR处理失败: {e}")
            raise HTTPException(status_code=500, detail=f"OCR处理失败: {str(e)}")
    
    def embed_text_to_pdf(self, input_pdf: str, output_pdf: str, ocr_data: List[Dict[str, Any]], remove_text_layer: bool = False) -> str:
        """
        将OCR文本嵌入到PDF中
        
        Args:
            input_pdf: 输入PDF路径
            output_pdf: 输出PDF路径
            ocr_data: OCR数据
            remove_text_layer: 是否先删除文本层（默认False）
            
        Returns:
            str: 输出PDF路径
        """
        try:
            logger.info(f"将OCR文本嵌入PDF，remove_text_layer={remove_text_layer}...")
            
            # 如果需要删除文本层，先创建纯图像PDF
            if remove_text_layer:
                logger.info("强制OCR模式：先删除原始文本层...")
                # 创建临时纯图像PDF
                image_pdf = output_pdf.replace(".pdf", "_image.pdf")
                image_pdf = self.remove_text_preserve_appearance(input_pdf, image_pdf, dpi=300)
                input_pdf = image_pdf  # 使用纯图像PDF作为输入
            
            # 使用自定义字体配置
            font_config = self.custom_font_config.get_font_config()
            font_name = font_config["font_name"]
            encoding = font_config["encoding"]
            font_type = font_config["font_type"]
            font_file = font_config["font_file"]
            
            logger.debug(f"使用自定义字体配置: {font_name}, {encoding}, {font_type}")
            
            doc = fitz.open(input_pdf)
            text_count = 0
            
            # 强制使用自定义字体文件
            if font_file and os.path.exists(font_file):
                logger.debug(f"强制使用自定义字体文件: {font_file}")
                # 为字体分配一个内部名称
                font_internal_name = "CustomFont"
                
                # 尝试在页面级别嵌入字体
                actual_font = font_internal_name
                font_embedded = False
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    try:
                        # 嵌入字体到页面
                        page.insert_font(fontfile=font_file, fontname=font_internal_name)
                        logger.debug(f"页面 {page_num+1} 字体嵌入成功")
                        font_embedded = True
                        break
                    except Exception as e:
                        logger.warning(f"页面 {page_num+1} 字体嵌入失败: {e}")
                
                if not font_embedded:
                    raise Exception(f"所有页面字体嵌入失败")
            else:
                # 没有字体文件，直接失败
                raise Exception(f"字体文件不存在: {font_file}")
            
            for page_data in ocr_data:
                page_num = page_data.get('page_number', 1) - 1  # 转换为0-based索引
                
                if page_num >= len(doc):
                    continue
                    
                page = doc[page_num]
                text = page_data.get('text', '').strip()
                
                if text:
                    # 获取页面尺寸
                    page_rect = page.rect
                    
                    # 在页面底部添加文本（使用透明文字，完全不可见但可搜索）
                    try:
                        # 创建一个覆盖大部分页面的文本区域
                        text_rect = fitz.Rect(
                            50, 50,  # 左上角
                            page_rect.width - 50, page_rect.height - 50  # 右下角
                        )
                        
                        # 使用TextWriter创建透明文字
                        text_writer = fitz.TextWriter(text_rect, opacity=0, color=(0, 0, 0))
                        
                        # 创建字体对象
                        if actual_font == "CustomFont":
                            # 使用嵌入的自定义字体
                            font_obj = fitz.Font(fontfile=font_file)
                        else:
                            # 使用内置字体
                            font_obj = fitz.Font(fontname=actual_font)
                        
                        # 使用fill_textbox方法填充文本，正确处理换行符
                        overflow_lines = text_writer.fill_textbox(
                            text_rect,
                            text,
                            font=font_obj,
                            fontsize=8,
                            align=0,  # 左对齐
                            warn=False  # 不警告溢出
                        )
                        
                        # 写入页面，使用render_mode=3使文本完全不可见但可搜索
                        text_writer.write_text(page, render_mode=3, overlay=True)
                        
                        if overflow_lines:
                            logger.warning(f"页面 {page_num+1} 部分文本溢出，未完全显示")
                        
                        text_count += 1
                        logger.debug(f"页面 {page_num+1} 文本嵌入成功")
                        
                    except Exception as e:
                        logger.error(f"页面 {page_num+1} 文本嵌入失败: {e}")
                        raise Exception(f"文本嵌入失败: {e}")
            
            # 保存PDF，确保字体嵌入
            doc.save(output_pdf, garbage=4, deflate=True, clean=True, expand=True)
            doc.close()
            
            logger.info(f"文本嵌入完成，共嵌入 {text_count} 页文本")
            
            return output_pdf
            
        except Exception as e:
            logger.error(f"文本嵌入失败: {e}")
            raise HTTPException(status_code=500, detail=f"文本嵌入失败: {str(e)}")
