"""
PDF 处理路由
"""
import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from services.pdf_ocr_proxy import PDFOCRProxy
from utils.file_utils import cleanup_temp_files

logger = logging.getLogger("pdf_ocr_proxy")

# 创建路由
router = APIRouter(prefix="/api", tags=["PDF处理"])

# 任务存储（生产环境应使用Redis或数据库）
processing_tasks: Dict[str, Any] = {}

# 认证
security = HTTPBearer()

# 全局代理实例
pdf_proxy = PDFOCRProxy()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证Bearer Token"""
    if credentials.credentials != settings.auth_token:
        logger.warning(f"认证失败: 无效的token")
        raise HTTPException(
            status_code=401,
            detail="无效的认证token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials


@router.post("/process-pdf")
async def process_pdf(
    pdf_file: UploadFile = File(...),
    force_ocr: bool = Form(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    token: str = Depends(verify_token)
):
    """
    处理PDF文件（异步版本）
    
    - **pdf_file**: 需要处理的PDF文件
    - **force_ocr**: 是否强制进行OCR处理，即使PDF已包含文本（默认: False）
    
    返回:
    - 202 Accepted: 任务已接收，后台处理中
    """
    if not pdf_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持PDF文件")
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 创建任务记录
    processing_tasks[task_id] = {
        "status": "accepted",
        "start_time": datetime.now().isoformat(),
        "message": "任务已接收，正在排队处理",
        "force_ocr": force_ocr
    }
    
    # 添加后台任务
    background_tasks.add_task(pdf_proxy.process_pdf_async, pdf_file, task_id, processing_tasks, force_ocr)
    
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "task_id": task_id,
            "message": "PDF已接收，正在后台处理",
            "force_ocr": force_ocr,
            "check_status": f"/api/tasks/{task_id}"
        }
    )


@router.post("/process-pdf-sync")
async def process_pdf_sync(
    pdf_file: UploadFile = File(...),
    force_ocr: bool = Form(False),
    token: str = Depends(verify_token)
):
    """
    同步处理PDF文件（向后兼容）
    
    - **pdf_file**: 需要处理的PDF文件
    - **force_ocr**: 是否强制进行OCR处理，即使PDF已包含文本（默认: False）
    
    返回:
    - JSON响应（如果无需OCR处理）
    - PDF文件（如果需要OCR处理）
    """
    if not pdf_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持PDF文件")
    
    try:
        # 同步处理PDF
        result = await pdf_proxy.process_pdf_sync(pdf_file, force_ocr)
        
        if result.get("needs_ocr", False):
            # 需要OCR处理，返回处理后的PDF文件
            output_file = result.get("output_file")
            if output_file and os.path.exists(output_file):
                # 读取文件内容并返回
                with open(output_file, 'rb') as f:
                    file_content = f.read()
                
                # 清理临时文件
                if output_file:
                    cleanup_temp_files(output_file)
                
                # 返回PDF文件
                from fastapi.responses import Response
                return Response(
                    content=file_content,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f"attachment; filename=ocr_processed_{pdf_file.filename}"
                    }
                )
            else:
                raise HTTPException(status_code=500, detail="OCR处理失败：输出文件不存在")
        else:
            # 无需OCR处理，返回JSON响应
            return result
            
    except Exception as e:
        logger.error(f"同步处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, token: str = Depends(verify_token)):
    """
    获取任务状态
    
    - **task_id**: 任务ID
    
    返回:
    - 任务状态信息
    """
    if task_id not in processing_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return processing_tasks[task_id]


@router.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


@router.get("/")
async def root():
    """根路径"""
    return {"message": "PDF OCR代理服务正在运行 🚀", "docs": "/docs"}
