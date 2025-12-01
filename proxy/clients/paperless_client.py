"""
Paperless API 客户端
修复 CSRF 问题的 Paperless 客户端
"""
import requests
import logging
from typing import Optional
from config import settings

logger = logging.getLogger("pdf_ocr_proxy")


class PaperlessClient:
    """Paperless API客户端 - 修复 CSRF 问题版本"""
    
    def __init__(self):
        # 清理URL末尾的斜杠
        base_url = settings.paperless_url
        if base_url and base_url.endswith('/'):
            base_url = base_url.rstrip('/')
        
        self.base_url = base_url
        self.api_key = settings.paperless_api_key
        self.session = requests.Session()
        self.csrf_token: Optional[str] = None
        
        # 配置会话
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Token {self.api_key}'
            })
    
    def _get_csrf_token(self) -> Optional[str]:
        """
        获取 CSRF token
        
        Returns:
            Optional[str]: CSRF token，如果获取失败返回 None
        """
        if not self.base_url:
            return None
            
        try:
            # 尝试多种方式获取 CSRF token
            urls_to_try = [
                f"{self.base_url}/api/documents/post_document/",
                f"{self.base_url}/api/documents/",
                f"{self.base_url}/api/",
                f"{self.base_url}/admin/login/"
            ]
            
            for url in urls_to_try:
                try:
                    response = self.session.get(url, timeout=10)
                    
                    # 从 cookies 中获取 CSRF token
                    if 'csrftoken' in self.session.cookies:
                        self.csrf_token = self.session.cookies['csrftoken']
                        logger.debug(f"成功获取 CSRF token: {self.csrf_token[:10]}...")
                        return self.csrf_token
                    
                    # 如果 cookies 中没有，尝试从响应头中获取
                    if 'X-CSRFToken' in response.headers:
                        self.csrf_token = response.headers['X-CSRFToken']
                        logger.debug(f"从响应头获取 CSRF token: {self.csrf_token[:10]}...")
                        return self.csrf_token
                        
                    # 尝试从 HTML 中提取 CSRF token
                    if 'text/html' in response.headers.get('content-type', ''):
                        import re
                        csrf_patterns = [
                            r'name="csrfmiddlewaretoken" value="([^"]+)"',
                            r'csrfToken:\s*"([^"]+)"',
                            r'"csrf_token":\s*"([^"]+)"'
                        ]
                        for pattern in csrf_patterns:
                            match = re.search(pattern, response.text)
                            if match:
                                self.csrf_token = match.group(1)
                                logger.debug(f"从HTML获取 CSRF token: {self.csrf_token[:10]}...")
                                return self.csrf_token
                                
                except Exception as e:
                    logger.debug(f"尝试从 {url} 获取 CSRF token 失败: {e}")
                    continue
            
            logger.warning("无法从 Paperless 获取 CSRF token")
            return None
                    
        except Exception as e:
            logger.error(f"获取 CSRF token 失败: {e}")
            return None
    
    def upload_document(self, file_path: str, filename: str) -> bool:
        """
        上传文档到 Paperless（根据官方文档修复）
        
        Args:
            file_path: 文件路径
            filename: 文件名
            
        Returns:
            bool: 上传是否成功
        """
        if not self.base_url or not self.api_key:
            logger.warning("Paperless配置不完整，跳过上传")
            return False
            
        try:
            # 获取 CSRF token
            csrf_token = self._get_csrf_token()
            
            # 准备请求头
            headers = {
                'Authorization': f'Token {self.api_key}'
            }
            
            # 如果获取到 CSRF token，添加到请求头
            if csrf_token:
                headers['X-CSRFToken'] = csrf_token
            
            with open(file_path, 'rb') as f:
                files = {'document': (filename, f, 'application/pdf')}
                
                response = self.session.post(
                    f"{self.base_url}/api/documents/post_document/",
                    files=files,
                    headers=headers,
                    timeout=60
                )
                
                # 根据官方文档，HTTP 200 表示文档消费过程已成功启动
                if response.status_code == 200:
                    # 检查响应内容类型
                    content_type = response.headers.get('content-type', '')
                    
                    if 'application/json' in content_type:
                        try:
                            # 尝试解析JSON响应
                            task_data = response.json()
                            if isinstance(task_data, dict):
                                task_id = task_data.get('task_id')
                                logger.info(f"文档消费任务已启动: {filename}, 任务ID: {task_id}")
                                logger.debug(f"任务响应: {task_data}")
                            else:
                                # 如果响应是字符串（如任务ID字符串）
                                logger.info(f"文档消费任务已启动: {filename}, 任务ID: {task_data}")
                            return True
                        except Exception as json_error:
                            # 如果JSON解析失败，可能是字符串响应
                            logger.info(f"文档消费任务已启动: {filename}, 任务ID: {response.text}")
                            return True
                    else:
                        # 如果不是JSON响应，可能是空响应或HTML响应
                        # 根据Paperless文档，HTTP 200表示成功启动，即使没有JSON响应
                        logger.info(f"文档消费任务已启动: {filename} (非JSON响应)")
                        logger.debug(f"响应内容类型: {content_type}")
                        logger.debug(f"响应内容: {response.text[:200] if response.text else '空响应'}")
                        return True
                        
                elif response.status_code == 201:
                    # 有些Paperless版本可能返回201
                    logger.info(f"文档成功上传到Paperless: {filename} (HTTP 201)")
                    return True
                        
                else:
                    logger.error(f"Paperless上传失败: {response.status_code} - {response.text}")
                    logger.debug(f"请求头: {headers}")
                    
                    # 如果是 CSRF 错误，尝试重新获取 token 并重试
                    if response.status_code == 403 and "CSRF" in response.text:
                        logger.info("检测到 CSRF 错误，尝试重新获取 token 并重试...")
                        # 清除旧的 CSRF token
                        self.csrf_token = None
                        # 重新获取 CSRF token
                        csrf_token = self._get_csrf_token()
                        
                        if csrf_token:
                            headers['X-CSRFToken'] = csrf_token
                            # 重新上传
                            f.seek(0)  # 重置文件指针
                            response = self.session.post(
                                f"{self.base_url}/api/documents/post_document/",
                                files=files,
                                headers=headers,
                                timeout=60
                            )
                            
                            if response.status_code == 200:
                                try:
                                    task_data = response.json()
                                    task_id = task_data.get('task_id')
                                    logger.info(f"重试后文档消费任务已启动: {filename}, 任务ID: {task_id}")
                                    return True
                                except Exception as json_error:
                                    logger.error(f"重试后解析任务响应失败: {json_error}")
                                    return False
                    
                    return False
                    
        except Exception as e:
            logger.error(f"Paperless上传异常: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        测试 Paperless 连接
        
        Returns:
            bool: 连接是否成功
        """
        if not self.base_url or not self.api_key:
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/documents/", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Paperless连接测试失败: {e}")
            return False
