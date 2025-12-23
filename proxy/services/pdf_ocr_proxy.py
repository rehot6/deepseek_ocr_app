"""
PDF OCR 代理服务
主业务逻辑服务
"""
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import UploadFile, HTTPException

from config import settings
from models.pdf_text_detector import PDFTextDetector
from services.ocr_embedder import OCRTextEmbedder
from clients.paperless_client import PaperlessClient
from utils.file_utils import create_temp_file, cleanup_temp_files, save_to_local_directory

logger = logging.getLogger("pdf_ocr_proxy")


class PDFOCRProxy:
    """PDF OCR代理服务"""
    
    def __init__(self):
        self.text_detector = PDFTextDetector()
        self.ocr_embedder = OCRTextEmbedder()
        self.paperless_client = PaperlessClient()
    
    async def process_pdf_sync(self, pdf_file: UploadFile, force_ocr: bool = False) -> Dict[str, Any]:
        """
        同步处理PDF文件
        
        Args:
            pdf_file: 上传的PDF文件
            force_ocr: 是否强制进行OCR处理，即使PDF已包含文本
            
        Returns:
            Dict: 处理结果，可能包含文件路径或JSON响应
        """
        try:
            # 创建临时文件
            input_pdf = create_temp_file(suffix=".pdf")
            output_pdf = None
            
            try:
                # 保存上传的文件到临时文件
                content = await pdf_file.read()
                with open(input_pdf, 'wb') as f:
                    f.write(content)
                
                # 1. 检测PDF是否已经包含有意义的文本
                logger.info(f"同步处理: 检测PDF文本内容，force_ocr={force_ocr}...")
                has_text = self.text_detector.has_meaningful_text(input_pdf)
                
                # 如果强制OCR或者PDF没有有意义的文本，则进行OCR处理
                needs_ocr = force_ocr or not has_text
                logger.info(f"同步处理: 文本检测结果 - has_text={has_text}, needs_ocr={needs_ocr}")
                
                if not needs_ocr:
                    logger.info(f"同步处理: PDF已包含有意义的文本，无需OCR处理")
                    
                    return {
                        "success": True,
                        "message": "PDF已包含有意义的文本，无需OCR处理",
                        "needs_ocr": False,
                        "force_ocr": force_ocr,
                        "has_text": has_text
                    }
                else:
                    if force_ocr:
                        logger.info(f"同步处理: 强制OCR处理，即使PDF已包含文本")
                    else:
                        logger.info(f"同步处理: PDF需要OCR处理")
                    
                    # 2. 调用OCR服务（异步）
                    ocr_data = await self.ocr_embedder.perform_ocr_async(input_pdf)
                    
                    # 3. 创建输出文件
                    output_pdf = create_temp_file(suffix=".pdf")
                    
                    # 4. 将OCR文本嵌入PDF（强制OCR时删除原始文本层）
                    result_pdf = self.ocr_embedder.embed_text_to_pdf(input_pdf, output_pdf, ocr_data, remove_text_layer=force_ocr)
                    
                    # 5. 保存到本地目录（如果启用）
                    saved_path = save_to_local_directory(result_pdf, pdf_file.filename)
                    
                    return {
                        "success": True,
                        "message": "OCR处理完成，文本已嵌入PDF",
                        "needs_ocr": True,
                        "force_ocr": force_ocr,
                        "has_text": has_text,
                        "output_file": result_pdf,
                        "local_saved_path": saved_path,
                        "ocr_data": {
                            "total_pages": len(ocr_data),
                            "pages_processed": len([p for p in ocr_data if p.get('text', '').strip()])
                        }
                    }
                    
            except Exception as e:
                logger.error(f"同步处理失败: {e}")
                raise
                
            finally:
                # 注意：同步处理中，如果返回文件，调用者需要负责清理
                # 这里只清理输入文件，输出文件由调用者处理
                if input_pdf:
                    cleanup_temp_files(input_pdf)
                    
        except Exception as e:
            logger.error(f"同步处理失败: {e}")
            raise
    
    async def process_pdf_async(self, pdf_file: UploadFile, task_id: str, processing_tasks: Dict[str, Any], force_ocr: bool = False) -> Dict[str, Any]:
        """
        异步处理PDF文件
        
        Args:
            pdf_file: 上传的PDF文件
            task_id: 任务ID
            processing_tasks: 任务存储字典
            force_ocr: 是否强制进行OCR处理，即使PDF已包含文本
            
        Returns:
            Dict: 处理结果
        """
        try:
            # 更新任务状态为处理中
            processing_tasks[task_id] = {
                "status": "processing",
                "start_time": datetime.now().isoformat(),
                "message": "正在处理PDF文件",
                "force_ocr": force_ocr
            }
            
            # 创建临时文件
            input_pdf = create_temp_file(suffix=".pdf")
            output_pdf = None
            
            try:
                # 保存上传的文件到临时文件
                content = await pdf_file.read()
                with open(input_pdf, 'wb') as f:
                    f.write(content)
                
                # 1. 检测PDF是否已经包含有意义的文本
                logger.info(f"任务 {task_id}: 检测PDF文本内容，force_ocr={force_ocr}...")
                has_text = self.text_detector.has_meaningful_text(input_pdf)
                
                # 如果强制OCR或者PDF没有有意义的文本，则进行OCR处理
                needs_ocr = force_ocr or not has_text
                logger.info(f"任务 {task_id}: 文本检测结果 - has_text={has_text}, needs_ocr={needs_ocr}")
                
                if not needs_ocr:
                    logger.info(f"任务 {task_id}: PDF已包含有意义的文本，无需OCR处理")
                    
                    # 上传到Paperless
                    paperless_success = self.paperless_client.upload_document(input_pdf, pdf_file.filename)
                    
                    # 保存到本地目录（如果启用）
                    saved_path = save_to_local_directory(input_pdf, pdf_file.filename)
                    
                    processing_tasks[task_id] = {
                        "status": "completed",
                        "end_time": datetime.now().isoformat(),
                        "message": "PDF已包含有意义的文本，无需OCR处理",
                        "paperless_uploaded": paperless_success,
                        "local_saved_path": saved_path,
                        "needs_ocr": False,
                        "force_ocr": force_ocr,
                        "has_text": has_text
                    }
                    
                    return {
                        "success": True,
                        "needs_ocr": False,
                        "paperless_uploaded": paperless_success,
                        "local_saved_path": saved_path,
                        "force_ocr": force_ocr,
                        "has_text": has_text
                    }
                else:
                    if force_ocr:
                        logger.info(f"任务 {task_id}: 强制OCR处理，即使PDF已包含文本")
                    else:
                        logger.info(f"任务 {task_id}: PDF需要OCR处理")
                    
                    # 2. 调用OCR服务（异步）
                    ocr_data = await self.ocr_embedder.perform_ocr_async(input_pdf)
                    
                    # 3. 创建输出文件
                    output_pdf = create_temp_file(suffix=".pdf")
                    
                    # 4. 将OCR文本嵌入PDF（强制OCR时删除原始文本层）
                    result_pdf = self.ocr_embedder.embed_text_to_pdf(input_pdf, output_pdf, ocr_data, remove_text_layer=force_ocr)
                    
                    # 5. 上传到Paperless（保持原文件名）
                    paperless_success = self.paperless_client.upload_document(result_pdf, pdf_file.filename)
                    
                    # 6. 保存到本地目录（如果启用）
                    saved_path = save_to_local_directory(result_pdf, pdf_file.filename)
                    
                    processing_tasks[task_id] = {
                        "status": "completed",
                        "end_time": datetime.now().isoformat(),
                        "message": "OCR处理完成，文本已嵌入PDF",
                        "paperless_uploaded": paperless_success,
                        "local_saved_path": saved_path,
                        "needs_ocr": True,
                        "force_ocr": force_ocr,
                        "has_text": has_text,
                        "ocr_data": {
                            "total_pages": len(ocr_data),
                            "pages_processed": len([p for p in ocr_data if p.get('text', '').strip()])
                        }
                    }
                    
                    return {
                        "success": True,
                        "needs_ocr": True,
                        "paperless_uploaded": paperless_success,
                        "local_saved_path": saved_path,
                        "force_ocr": force_ocr,
                        "has_text": has_text
                    }
                    
            except Exception as e:
                logger.error(f"任务 {task_id}: 处理失败: {e}")
                processing_tasks[task_id] = {
                    "status": "failed",
                    "end_time": datetime.now().isoformat(),
                    "message": f"处理失败: {str(e)}",
                    "force_ocr": force_ocr
                }
                # 不重新抛出异常，避免影响已开始的响应
                return {
                    "success": False,
                    "error": str(e),
                    "force_ocr": force_ocr
                }
                
            finally:
                # 清理临时文件
                cleanup_temp_files(input_pdf, output_pdf)
                    
        except Exception as e:
            logger.error(f"任务 {task_id}: 处理失败: {e}")
            processing_tasks[task_id] = {
                "status": "failed",
                "end_time": datetime.now().isoformat(),
                "message": f"处理失败: {str(e)}",
                "force_ocr": force_ocr
            }
            # 不重新抛出异常，避免影响已开始的响应
            return {
                "success": False,
                "error": str(e),
                "force_ocr": force_ocr
            }
