import os
import tempfile
import requests
import fitz  # PyMuPDF
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

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
            
            print(f"📊 PDF文本检测结果:")
            print(f"   - 总字符数: {total_chars}")
            print(f"   - 中文字符数: {chinese_chars}")
            print(f"   - 单词数: {total_words}")
            print(f"   - 有意义的文本: {'是' if has_text else '否'}")
            
            return has_text
            
        except Exception as e:
            print(f"❌ PDF文本检测失败: {e}")
            return False

class OCRTextEmbedder:
    """OCR文本嵌入器，用于将OCR结果嵌入到PDF中"""
    
    def __init__(self):
        self.backend_url = "http://localhost:8000"  # 后端服务地址
    
    def perform_ocr(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        调用后端OCR服务处理PDF
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            List[Dict]: OCR结果数据
        """
        try:
            print("🔍 调用后端OCR服务...")
            
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
                    print(f"✅ OCR处理完成，共 {result.get('total_pages', 0)} 页")
                    
                    # 详细输出OCR返回内容
                    pages = result.get('pages', [])
                    print(f"📄 OCR返回的页面数据:")
                    for i, page_data in enumerate(pages):
                        text = page_data.get('text', '')
                        print(f"   - 页面 {i+1}: 文本长度={len(text)}, 内容={repr(text[:100])}...")
                    
                    return pages
                else:
                    print(f"❌ OCR服务返回错误: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=500, detail=f"OCR服务错误: {response.text}")
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ 连接OCR服务失败: {e}")
            raise HTTPException(status_code=503, detail="OCR服务不可用")
        except Exception as e:
            print(f"❌ OCR处理失败: {e}")
            raise HTTPException(status_code=500, detail=f"OCR处理失败: {str(e)}")
    
    def embed_text_to_pdf(self, input_pdf: str, output_pdf: str, ocr_data: List[Dict[str, Any]]) -> str:
        """
        将OCR文本嵌入到PDF中
        
        Args:
            input_pdf: 输入PDF路径
            output_pdf: 输出PDF路径
            ocr_data: OCR数据
            
        Returns:
            str: 输出PDF路径
        """
        try:
            print("📝 将OCR文本嵌入PDF...")
            
            doc = fitz.open(input_pdf)
            text_count = 0
            
            for page_data in ocr_data:
                page_num = page_data.get('page_number', 1) - 1  # 转换为0-based索引
                
                if page_num >= len(doc):
                    continue
                    
                page = doc[page_num]
                text = page_data.get('text', '').strip()
                
                if text:
                    # 获取页面尺寸
                    page_rect = page.rect
                    
                    # 在页面底部添加文本（使用insert_textbox确保完整文本嵌入）
                    try:
                        # 创建一个覆盖大部分页面的文本区域
                        text_rect = fitz.Rect(
                            50, 50,  # 左上角
                            page_rect.width - 50, page_rect.height - 50  # 右下角
                        )
                        
                        # 使用insert_textbox，它会正确处理文本换行和完整嵌入
                        result = page.insert_textbox(
                            text_rect,
                            text,
                            fontsize=8,
                            fontname="china-ss",  # 使用简体中文字体
                            color=(0, 0, 0),  # 黑色文本
                            align=0,  # 左对齐
                            overlay=True
                        )
                        
                        if result > 0:
                            text_count += 1
                            print(f"✅ 页面 {page_num+1} 文本嵌入成功，完整文本已嵌入")
                        else:
                            # 如果文本区域太小，尝试使用更大的区域
                            print(f"⚠ 页面 {page_num+1} 文本区域太小，尝试使用更大的区域")
                            # 使用整个页面区域
                            full_rect = fitz.Rect(20, 20, page_rect.width - 20, page_rect.height - 20)
                            result2 = page.insert_textbox(
                                full_rect,
                                text,
                                fontsize=6,  # 使用更小的字体
                                fontname="china-ss",
                                color=(0, 0, 0),
                                align=0,
                                overlay=True
                            )
                            if result2 > 0:
                                text_count += 1
                                print(f"✅ 页面 {page_num+1} 文本嵌入成功（使用小字体）")
                            else:
                                text_count += 1
                                print(f"⚠ 页面 {page_num+1} 文本可能未完全显示，但部分文本已嵌入")
                    except Exception as e:
                        print(f"⚠ 页面 {page_num+1} 文本嵌入失败: {e}")
            
            # 保存PDF，确保字体嵌入
            doc.save(output_pdf, garbage=4, deflate=True, clean=True, expand=True)
            doc.close()
            
            print(f"✅ 文本嵌入完成，共嵌入 {text_count} 页文本")
            return output_pdf
            
        except Exception as e:
            print(f"❌ 文本嵌入失败: {e}")
            raise HTTPException(status_code=500, detail=f"文本嵌入失败: {str(e)}")

class PDFOCRProxy:
    """PDF OCR代理服务"""
    
    def __init__(self):
        self.text_detector = PDFTextDetector()
        self.ocr_embedder = OCRTextEmbedder()
    
    def process_pdf(self, pdf_file: UploadFile) -> Dict[str, Any]:
        """
        处理PDF文件
        
        Args:
            pdf_file: 上传的PDF文件
            
        Returns:
            Dict: 处理结果
        """
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_input:
            content = pdf_file.file.read()
            tmp_input.write(content)
            input_pdf = tmp_input.name
        
        output_pdf = None
        try:
            # 1. 检测PDF是否已经包含有意义的文本
            print("🔍 检测PDF文本内容...")
            has_text = self.text_detector.has_meaningful_text(input_pdf)
            
            if has_text:
                print("✅ PDF已包含有意义的文本，无需OCR处理")
                return {
                    "success": True,
                    "needs_ocr": False,
                    "message": "PDF已包含有意义的文本，无需OCR处理",
                    "file_path": input_pdf  # 返回原始文件
                }
            else:
                print("📄 PDF需要OCR处理")
                
                # 2. 调用OCR服务
                ocr_data = self.ocr_embedder.perform_ocr(input_pdf)
                
                # 3. 创建输出文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_output:
                    output_pdf = tmp_output.name
                
                # 4. 将OCR文本嵌入PDF
                result_pdf = self.ocr_embedder.embed_text_to_pdf(input_pdf, output_pdf, ocr_data)
                
                return {
                    "success": True,
                    "needs_ocr": True,
                    "message": "OCR处理完成，文本已嵌入PDF",
                    "file_path": result_pdf,
                    "ocr_data": {
                        "total_pages": len(ocr_data),
                        "pages_processed": len([p for p in ocr_data if p.get('text', '').strip()])
                    }
                }
                
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
        
        finally:
            # 清理临时文件
            try:
                if os.path.exists(input_pdf):
                    os.remove(input_pdf)
            except:
                pass

# FastAPI应用
app = FastAPI(
    title="PDF OCR代理服务",
    description="智能PDF OCR代理服务 - 自动检测文本并嵌入OCR结果",
    version="1.0.0"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局代理实例
pdf_proxy = PDFOCRProxy()

@app.get("/")
async def root():
    return {"message": "PDF OCR代理服务正在运行 🚀", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/process-pdf")
async def process_pdf(pdf_file: UploadFile = File(...)):
    """
    处理PDF文件
    
    - **pdf_file**: 需要处理的PDF文件
    
    返回:
    - 如果PDF已包含有意义的文本: 返回原始PDF
    - 如果PDF需要OCR: 返回嵌入OCR文本的PDF
    """
    if not pdf_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持PDF文件")
    
    try:
        # 处理PDF
        result = pdf_proxy.process_pdf(pdf_file)
        
        if result["success"]:
            if result.get("needs_ocr", False):
                # 返回处理后的PDF文件
                output_path = result["file_path"]
                filename = f"ocr_processed_{pdf_file.filename}"
                
                return StreamingResponse(
                    open(output_path, "rb"),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            else:
                # 返回原始PDF文件
                return JSONResponse({
                    "success": True,
                    "message": result["message"],
                    "needs_ocr": False
                })
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "处理失败"))
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
