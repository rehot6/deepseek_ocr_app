"""
PDF 处理路由
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from services.pdf_ocr_proxy import PDFOCRProxy

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
    background_tasks: BackgroundTasks = BackgroundTasks(),
    token: str = Depends(verify_token)
):
    """
    处理PDF文件（异步版本）
    
    - **pdf_file**: 需要处理的PDF文件
    
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
        "message": "任务已接收，正在排队处理"
    }
    
    # 添加后台任务
    background_tasks.add_task(pdf_proxy.process_pdf_async, pdf_file, task_id, processing_tasks)
    
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "task_id": task_id,
            "message": "PDF已接收，正在后台处理",
            "check_status": f"/api/tasks/{task_id}"
        }
    )


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
