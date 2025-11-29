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
            
            print(f"📊 字体分析结果:")
            print(f"   - 检测到 {len(font_info['fonts'])} 种字体")
            print(f"   - 推荐字体: {font_info['recommended_font']}")
            print(f"   - 包含CID字体: {font_info['has_cid_fonts']}")
            print(f"   - 包含Identity-H编码: {font_info['has_identity_h']}")
            
            for font in font_info["fonts"]:
                print(f"     * 字体: {font['name']}")
                print(f"       - 编码: {font['encoding']}")
                print(f"       - 类型: {font['type']}")
                print(f"       - 子类型: {font['subtype']}")
                print(f"       - 扩展名: {font['extension']}")
                print(f"       - XREF: {font['xref']}")
                print(f"       - 有字体数据: {font.get('has_buffer', False)}")
            
            return font_info
            
        except Exception as e:
            print(f"❌ 字体分析失败: {e}")
            return {
                "fonts": [],
                "recommended_font": "china-ss",
                "has_cid_fonts": False,
                "has_identity_h": False,
                "font_details": []
            }

class CustomFontConfig:
    """自定义字体配置"""
    
    def __init__(self, font_name="NotoSansCJK", encoding="Identity-H", font_type="Type0", font_file="fonts/NotoSansCJK-Regular.ttc"):
        self.font_name = font_name
        self.encoding = encoding
        self.font_type = font_type
        self.font_file = font_file  # 字体文件路径
    
    def get_font_config(self):
        """获取字体配置"""
        return {
            "font_name": self.font_name,
            "encoding": self.encoding,
            "font_type": self.font_type,
            "font_file": self.font_file
        }

class OCRTextEmbedder:
    """OCR文本嵌入器，用于将OCR结果嵌入到PDF中"""
    
    def __init__(self, custom_font_config=None):
        self.backend_url = "http://localhost:8000"  # 后端服务地址
        self.font_analyzer = FontAnalyzer()
        self.custom_font_config = custom_font_config or CustomFontConfig()
    
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
            
            # 使用自定义字体配置
            font_config = self.custom_font_config.get_font_config()
            font_name = font_config["font_name"]
            encoding = font_config["encoding"]
            font_type = font_config["font_type"]
            font_file = font_config["font_file"]
            
            print(f"🎨 使用自定义字体配置:")
            print(f"   - 字体名称: {font_name}")
            print(f"   - 编码: {encoding}")
            print(f"   - 类型: {font_type}")
            if font_file:
                print(f"   - 字体文件: {font_file}")
            
            doc = fitz.open(input_pdf)
            text_count = 0
            
            # 强制使用自定义字体文件
            if font_file and os.path.exists(font_file):
                print(f"📦 强制使用自定义字体文件: {font_file}")
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
                        print(f"✅ 页面 {page_num+1} 字体嵌入成功")
                        font_embedded = True
                        break
                    except Exception as e:
                        print(f"⚠ 页面 {page_num+1} 字体嵌入失败: {e}")
                
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
                            print(f"⚠ 页面 {page_num+1} 部分文本溢出，未完全显示")
                        
                        text_count += 1
                        print(f"✅ 页面 {page_num+1} 文本嵌入成功，完整文本已嵌入")
                        print(f"   - 使用字体: {actual_font}")
                        print(f"   - 透明度: 0 (完全透明)")
                        print(f"   - 渲染模式: 3 (完全不可见但可搜索)")
                        
                    except Exception as e:
                        print(f"❌ 页面 {page_num+1} 文本嵌入失败: {e}")
                        raise Exception(f"文本嵌入失败: {e}")
            
            # 保存PDF，确保字体嵌入
            doc.save(output_pdf, garbage=4, deflate=True, clean=True, expand=True)
            doc.close()
            
            print(f"✅ 文本嵌入完成，共嵌入 {text_count} 页文本")
            print(f"🎨 最终使用的字体配置:")
            print(f"   - 配置字体: {font_name}")
            print(f"   - 实际字体: {actual_font}")
            print(f"   - 编码: {encoding}")
            print(f"   - 类型: {font_type}")
            if font_file:
                print(f"   - 字体文件: {font_file}")
            
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
