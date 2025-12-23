"""
OCR文本嵌入器
用于将OCR结果嵌入到PDF中
"""
import os
import httpx
import fitz  # PyMuPDF
import logging
import asyncio
from typing import List, Dict, Any
from fastapi import HTTPException
from pathlib import Path

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
    
    async def perform_ocr_async(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        异步调用后端OCR服务处理PDF
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            List[Dict]: OCR结果数据
        """
        try:
            logger.info("异步调用后端OCR服务...")
            
            # 获取PDF页数以计算动态超时
            page_count = 0
            try:
                with fitz.open(pdf_path) as doc:
                    page_count = len(doc)
                logger.info(f"PDF页数: {page_count}")
            except Exception as e:
                logger.warning(f"无法获取PDF页数: {e}")
                page_count = 10  # 默认值
            
            # 动态计算超时时间
            # 基础超时60秒 + 每页10秒，最大不超过60分钟（3600秒）
            base_timeout = 60
            per_page_timeout = 10
            dynamic_timeout = base_timeout + (page_count * per_page_timeout)
            dynamic_timeout = min(dynamic_timeout, 3600)  # 最大60分钟
            
            logger.info(f"动态超时设置: {dynamic_timeout}秒 (页数: {page_count})")
            
            # 使用httpx异步客户端
            timeout = httpx.Timeout(dynamic_timeout, connect=10.0)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 读取PDF文件
                with open(pdf_path, 'rb') as f:
                    files = {'pdf_file': ('input.pdf', f, 'application/pdf')}
                    data = {
                        'mode': 'plain_ocr',
                        'output_format': 'json',
                        'dpi': 144
                    }
                    
                    # 发送异步请求到后端OCR服务
                    response = await client.post(
                        f"{self.backend_url}/api/process-pdf",
                        files=files,
                        data=data
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
                        
        except httpx.RequestError as e:
            logger.error(f"连接OCR服务失败: {e}")
            raise HTTPException(status_code=503, detail="OCR服务不可用")
        except Exception as e:
            logger.error(f"OCR处理失败: {e}")
            raise HTTPException(status_code=500, detail=f"OCR处理失败: {str(e)}")
    
    def perform_ocr(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        同步调用后端OCR服务处理PDF（向后兼容）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            List[Dict]: OCR结果数据
        """
        # 在事件循环中运行异步版本
        try:
            return asyncio.run(self.perform_ocr_async(pdf_path))
        except RuntimeError as e:
            # 如果已经在事件循环中，使用不同的方法
            if "cannot be called from a running event loop" in str(e):
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.perform_ocr_async(pdf_path))
                finally:
                    loop.close()
            else:
                raise
    
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
            
            failed_pages = []
            successful_pages = []
            
            for page_data in ocr_data:
                page_num = page_data.get('page_number', 1) - 1  # 转换为0-based索引
                
                if page_num >= len(doc):
                    logger.warning(f"页面编号 {page_num+1} 超出PDF范围，跳过")
                    continue
                    
                page = doc[page_num]
                text = page_data.get('text', '').strip()
                
                if not text:
                    logger.debug(f"页面 {page_num+1} 没有文本内容，跳过")
                    continue
                
                # 获取页面尺寸
                page_rect = page.rect
                
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
                        logger.warning(f"页面 {page_num+1} 部分文本溢出，未完全显示 ({len(overflow_lines)} 行未显示)")
                        # 记录部分成功
                        successful_pages.append({
                            'page': page_num + 1,
                            'status': 'partial',
                            'lines_embedded': len(text.split('\n')) - len(overflow_lines),
                            'lines_total': len(text.split('\n')),
                            'overflow_lines': len(overflow_lines)
                        })
                    else:
                        successful_pages.append({
                            'page': page_num + 1,
                            'status': 'success',
                            'lines_embedded': len(text.split('\n'))
                        })
                    
                    text_count += 1
                    logger.debug(f"页面 {page_num+1} 文本嵌入成功")
                    
                except Exception as e:
                    # 页面级错误处理：记录失败但继续处理其他页面
                    error_msg = str(e)
                    logger.error(f"页面 {page_num+1} 文本嵌入失败: {error_msg}")
                    failed_pages.append({
                        'page': page_num + 1,
                        'error': error_msg,
                        'text_length': len(text),
                        'line_count': len(text.split('\n'))
                    })
                    
                    # 尝试使用更小的字体或不同的方法
                    logger.warning(f"页面 {page_num+1} 嵌入失败，跳过此页面")
                    continue
            
            # 记录处理结果
            total_pages = len(ocr_data)
            success_count = len(successful_pages)
            fail_count = len(failed_pages)
            
            logger.info(f"文本嵌入完成统计: 总页数={total_pages}, 成功={success_count}, 失败={fail_count}, 部分成功={len([p for p in successful_pages if p['status'] == 'partial'])}")
            
            if failed_pages:
                logger.warning(f"以下页面嵌入失败: {[p['page'] for p in failed_pages]}")
                for failed in failed_pages:
                    logger.warning(f"  页面 {failed['page']}: {failed['error']}")
            
            if success_count == 0 and total_pages > 0:
                # 如果所有页面都失败，抛出异常
                raise Exception(f"所有页面文本嵌入失败，共 {fail_count} 页")
            
            # 保存PDF，确保字体嵌入
            doc.save(output_pdf, garbage=4, deflate=True, clean=True, expand=True)
            doc.close()
            
            logger.info(f"文本嵌入完成，共嵌入 {text_count} 页文本")
            
            return output_pdf
            
        except Exception as e:
            logger.error(f"文本嵌入失败: {e}")
            raise HTTPException(status_code=500, detail=f"文本嵌入失败: {str(e)}")
