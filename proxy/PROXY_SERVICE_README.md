# PDF OCR 代理服务

这是一个智能PDF OCR代理服务，能够自动检测PDF是否已经包含有意义的文本，并根据需要调用OCR服务将文本嵌入到PDF中。

## 功能特性

- 🔍 **智能文本检测**: 自动检测PDF是否包含有意义的文本
- 📄 **OCR处理**: 调用后端DeepSeek-OCR服务进行OCR处理
- 📝 **文本嵌入**: 将OCR结果以不可见但可搜索的方式嵌入PDF
- 🌐 **RESTful API**: 提供简单的HTTP API接口
- 🚀 **高性能**: 使用FastAPI框架，支持异步处理

## 安装依赖

```bash
pip install fastapi uvicorn requests PyMuPDF
```

## 启动服务

### 1. 启动后端OCR服务 (端口8000)
```bash
cd backend
python main.py
```

### 2. 启动代理服务 (端口8001)
```bash
python proxy_service.py
```

## API 使用

### 处理PDF文件

**端点**: `POST /api/process-pdf`

**参数**:
- `pdf_file`: PDF文件 (multipart/form-data)

**响应**:

**情况1: PDF已包含有意义的文本**
```json
{
  "success": true,
  "message": "PDF已包含有意义的文本，无需OCR处理",
  "needs_ocr": false
}
```

**情况2: PDF需要OCR处理**
- 返回处理后的PDF文件 (application/pdf)
- 文件名格式: `ocr_processed_原文件名.pdf`

## 使用示例

### Python 客户端

```python
import requests

def process_pdf(file_path):
    url = "http://localhost:8001/api/process-pdf"
    
    with open(file_path, 'rb') as f:
        files = {'pdf_file': ('document.pdf', f, 'application/pdf')}
        response = requests.post(url, files=files)
    
    if response.status_code == 200:
        content_type = response.headers.get('content-type', '')
        
        if 'application/json' in content_type:
            # 无需OCR处理
            result = response.json()
            print(f"无需OCR: {result['message']}")
        elif 'application/pdf' in content_type:
            # 已处理OCR，保存结果
            with open('processed_document.pdf', 'wb') as f:
                f.write(response.content)
            print("OCR处理完成，文件已保存")
    else:
        print(f"处理失败: {response.text}")

# 使用示例
process_pdf("my_document.pdf")
```

### cURL 示例

```bash
curl -X POST \
  http://localhost:8001/api/process-pdf \
  -F "pdf_file=@document.pdf" \
  -o processed_document.pdf
```

## 文本检测标准

代理服务使用以下标准判断PDF是否包含有意义的文本：

- **最少字符数**: 10个字符
- **最少中文字符**: 5个中文字符
- **最少单词数**: 3个单词

满足任一条件即认为PDF已包含有意义的文本。

## 文本嵌入方式

OCR文本以以下方式嵌入PDF：

- **位置**: 页面底部
- **字体**: 简体中文宋体 (china-ss)
- **大小**: 8pt
- **渲染模式**: 不可见但可搜索 (render_mode=3)
- **颜色**: 黑色

## 错误处理

- **400**: 文件格式错误（非PDF文件）
- **500**: 内部服务器错误
- **503**: OCR服务不可用

## 配置说明

### 代理服务配置
- 端口: 8001
- 后端OCR服务地址: http://localhost:8000
- 超时时间: 5分钟

### 文本检测阈值
可在 `PDFTextDetector` 类中调整：
```python
self.min_meaningful_chars = 10  # 最少有意义的字符数
self.min_chinese_chars = 5      # 最少中文字符数
self.min_word_count = 3         # 最少单词数
```

## 测试

运行测试脚本验证服务：

```bash
python test_proxy_service.py
```

## 部署建议

1. **生产环境**: 使用Docker容器化部署
2. **负载均衡**: 多实例部署支持高并发
3. **监控**: 添加健康检查和性能监控
4. **日志**: 配置结构化日志记录

## 注意事项

- 确保后端OCR服务在端口8000运行
- 代理服务需要访问后端OCR服务
- 大文件处理可能需要较长时间
- 临时文件会在处理完成后自动清理
