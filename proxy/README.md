# PDF OCR 代理服务

这是一个智能PDF OCR代理服务，能够自动检测PDF是否已经包含有意义的文本，并根据需要调用OCR服务将文本嵌入到PDF中。支持异步处理和自动转发到Paperless。

## 主要特性

- 🔐 **安全认证**: Bearer Token认证保护API
- ⚡ **异步处理**: 立即响应，后台处理OCR
- 📄 **智能OCR**: 自动检测PDF文本内容，按需OCR
- 📝 **文本嵌入**: 将OCR结果以不可见但可搜索的方式嵌入PDF
- 📤 **Paperless集成**: 自动转发处理后的文档到Paperless
- 🌐 **RESTful API**: 提供简单的HTTP API接口
- 🚀 **高性能**: 使用FastAPI框架，支持异步处理

## 环境变量配置

服务通过以下环境变量进行配置：

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `AUTH_TOKEN` | API认证token | `default_token` |
| `PAPERLESS_URL` | Paperless服务地址 | - |
| `PAPERLESS_API_KEY` | Paperless API密钥 | - |
| `BACKEND_OCR_URL` | 后端OCR服务地址 | `http://localhost:8000` |
| `LOG_LEVEL` | 日志级别 (DEBUG/INFO/WARNING/ERROR) | `INFO` |

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务

### 1. 设置环境变量
```bash
export AUTH_TOKEN="your_secure_token"
export PAPERLESS_URL="https://your-paperless-instance"
export PAPERLESS_API_KEY="your_paperless_api_key"
export BACKEND_OCR_URL="http://localhost:8000"
export LOG_LEVEL="INFO"
```

### 2. 启动服务
```bash
python proxy_service.py
```

## Docker 部署

### 构建镜像
```bash
docker build -t pdf-ocr-proxy .
```

### 运行容器
```bash
docker run -d \
  -p 8001:8001 \
  -e AUTH_TOKEN="your_secure_token" \
  -e PAPERLESS_URL="https://your-paperless-instance" \
  -e PAPERLESS_API_KEY="your_paperless_api_key" \
  -e BACKEND_OCR_URL="http://host.docker.internal:8000" \
  -e LOG_LEVEL="INFO" \
  --name pdf-ocr-proxy \
  pdf-ocr-proxy
```

## API 使用

### 认证
所有API端点都需要Bearer Token认证：
```
Authorization: Bearer your_token_here
```

### 异步处理PDF文件（推荐）

**端点**: `POST /api/process-pdf`

**参数**:
- `pdf_file`: PDF文件 (multipart/form-data)

**响应** (202 Accepted):
```json
{
  "status": "accepted",
  "task_id": "uuid-string",
  "message": "PDF已接收，正在后台处理",
  "check_status": "/api/tasks/uuid-string"
}
```

**查询任务状态**:
```bash
GET /api/tasks/{task_id}
```

**任务状态响应**:
```json
{
  "status": "completed",
  "start_time": "2024-01-01T00:00:00",
  "end_time": "2024-01-01T00:01:30",
  "message": "OCR处理完成，文本已嵌入PDF",
  "paperless_uploaded": true,
  "needs_ocr": true,
  "ocr_data": {
    "total_pages": 10,
    "pages_processed": 10
  }
}
```

### 同步处理PDF文件（向后兼容）

**端点**: `POST /api/process-pdf-sync`

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

### cURL 示例

#### 异步处理（推荐）
```bash
# 提交PDF处理任务
curl -X POST \
  http://localhost:8001/api/process-pdf \
  -H "Authorization: Bearer your_token_here" \
  -F "pdf_file=@document.pdf"

# 查询任务状态
curl -X GET \
  http://localhost:8001/api/tasks/task-uuid-here \
  -H "Authorization: Bearer your_token_here"
```

#### 同步处理（向后兼容）
```bash
curl -X POST \
  http://localhost:8001/api/process-pdf-sync \
  -H "Authorization: Bearer your_token_here" \
  -F "pdf_file=@document.pdf" \
  -o processed_document.pdf
```

### Python 客户端

```python
import requests

class PDFOCRClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def process_pdf_async(self, file_path):
        """异步处理PDF"""
        with open(file_path, 'rb') as f:
            files = {'pdf_file': ('document.pdf', f, 'application/pdf')}
            response = requests.post(
                f"{self.base_url}/api/process-pdf",
                files=files,
                headers=self.headers
            )
        
        if response.status_code == 202:
            return response.json()  # 返回任务信息
        else:
            raise Exception(f"提交失败: {response.text}")
    
    def get_task_status(self, task_id):
        """查询任务状态"""
        response = requests.get(
            f"{self.base_url}/api/tasks/{task_id}",
            headers=self.headers
        )
        return response.json()

# 使用示例
client = PDFOCRClient("http://localhost:8001", "your_token_here")

# 异步处理
task_info = client.process_pdf_async("my_document.pdf")
print(f"任务已提交: {task_info['task_id']}")

# 查询状态
import time
while True:
    status = client.get_task_status(task_info['task_id'])
    if status['status'] in ['completed', 'failed']:
        print(f"处理完成: {status}")
        break
    time.sleep(2)
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
- **401**: 认证失败
- **404**: 任务不存在
- **500**: 内部服务器错误
- **503**: OCR服务不可用

## 日志配置

通过 `LOG_LEVEL` 环境变量控制日志级别：
- `DEBUG`: 详细调试信息
- `INFO`: 一般信息（默认）
- `WARNING`: 警告信息
- `ERROR`: 错误信息

## 注意事项

- 确保后端OCR服务在配置的地址运行
- 代理服务需要访问后端OCR服务
- 大文件处理可能需要较长时间
- 临时文件会在处理完成后自动清理
- 生产环境建议使用Redis或数据库存储任务状态

## 健康检查

服务提供健康检查端点：
```bash
curl http://localhost:8001/health
```

响应：
```json
{"status": "healthy"}
```

## 故障排除

1. **认证失败**: 检查 `AUTH_TOKEN` 环境变量设置
2. **OCR服务不可用**: 检查 `BACKEND_OCR_URL` 和后端服务状态
3. **Paperless上传失败**: 检查 `PAPERLESS_URL` 和 `PAPERLESS_API_KEY` 配置
4. **字体嵌入失败**: 确保字体文件存在于 `fonts/` 目录


```bash
# 提交PDF处理任务
curl -X POST \
  http://localhost:8001/api/process-pdf \
  -H "Authorization: Bearer U6drUduBRoM1vGga7Di2cVse7jiURNsDZUGGDcEyofTOO7F66KbBbqSeILfTfFg3" \
  -F "pdf_file=@test/GB∕T37964-2019信息安全技术个人信息去标识化指南.pdf"

# 查询任务状态
curl -X GET \
  http://localhost:8001/api/tasks/task-uuid-here \
  -H "Authorization: Bearer your_token_here"
```