#!/usr/bin/env python3
"""
PDF批量处理脚本
用于处理renamed_pdfs目录中的PDF文件，使用强制OCR转换
"""

import os
import sys
import time
import requests
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_processing.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("pdf_batch_processor")


class PDFBatchProcessor:
    """PDF批量处理器"""
    
    def __init__(self, base_url: str, auth_token: str):
        """
        初始化处理器
        
        Args:
            base_url: 代理服务基础URL (如: http://localhost:8001)
            auth_token: 认证token
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {"Authorization": f"Bearer {auth_token}"}
        # 使用连接池和重试策略
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 配置重试策略
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置合理的超时
        self.session.timeout = (10, 30)  # 连接超时10秒，读取超时30秒
        
        # 处理统计
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None
        }
        
        # 结果存储
        self.results = []
    
    def process_pdf_async(self, pdf_path: Path, force_ocr: bool = True) -> Dict[str, Any]:
        """
        异步处理单个PDF文件
        
        Args:
            pdf_path: PDF文件路径
            force_ocr: 是否强制OCR处理
            
        Returns:
            Dict: 处理结果
        """
        try:
            logger.info(f"开始处理: {pdf_path.name}")
            
            # 准备请求数据
            files = {'pdf_file': (pdf_path.name, open(pdf_path, 'rb'), 'application/pdf')}
            data = {'force_ocr': 'true' if force_ocr else 'false'}
            
            # 发送异步处理请求
            response = self.session.post(
                f"{self.base_url}/api/process-pdf",
                files=files,
                data=data,
                timeout=30  # 30秒超时
            )
            
            if response.status_code == 202:
                task_info = response.json()
                task_id = task_info.get('task_id')
                logger.info(f"任务已提交: {task_id}")
                
                # 监控任务状态
                return self._monitor_task(task_id, pdf_path.name)
            else:
                error_msg = f"提交失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    "file": pdf_path.name,
                    "status": "failed",
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            error_msg = f"处理异常: {str(e)}"
            logger.error(error_msg)
            return {
                "file": pdf_path.name,
                "status": "failed",
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
    
    def _monitor_task(self, task_id: str, filename: str, max_wait: int = 3600) -> Dict[str, Any]:
        """
        监控异步任务状态
        
        Args:
            task_id: 任务ID
            filename: 文件名
            max_wait: 最大等待时间（秒），默认3600秒（60分钟）
            
        Returns:
            Dict: 任务结果
        """
        start_time = time.time()
        check_interval = 30  # 增加检查间隔到30秒，大幅减少查询频率
        consecutive_errors = 0  # 连续错误计数
        max_consecutive_errors = 5  # 增加最大连续错误次数
        
        logger.info(f"开始监控任务: {task_id}，最大等待时间: {max_wait}秒")
        
        while time.time() - start_time < max_wait:
            try:
                # 使用独立的请求而不是session，避免连接池问题
                response = requests.get(
                    f"{self.base_url}/api/tasks/{task_id}",
                    headers=self.headers,
                    timeout=30  # 增加超时到30秒
                )
                
                if response.status_code == 200:
                    task_status = response.json()
                    status = task_status.get('status')
                    
                    if status in ['completed', 'failed']:
                        # 任务完成或失败
                        result = {
                            "file": filename,
                            "task_id": task_id,
                            "status": status,
                            "details": task_status,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        if status == 'completed':
                            logger.info(f"任务完成: {filename}")
                        else:
                            error_msg = task_status.get('message', '未知错误')
                            logger.error(f"任务失败: {filename} - {error_msg}")
                        
                        return result
                    else:
                        # 任务仍在处理中
                        elapsed = int(time.time() - start_time)
                        # 每5分钟记录一次进度，而不是每次检查都记录
                        if elapsed % 300 == 0:  # 每5分钟
                            logger.info(f"任务处理中: {filename} ({elapsed//60}分{elapsed%60}秒)")
                        consecutive_errors = 0  # 重置错误计数
                
                else:
                    logger.warning(f"查询任务状态失败: {response.status_code}")
                    consecutive_errors += 1
                    
            except requests.exceptions.RequestException as e:
                # 网络相关错误
                consecutive_errors += 1
                if consecutive_errors <= max_consecutive_errors:
                    logger.warning(f"查询任务状态网络错误 ({consecutive_errors}/{max_consecutive_errors}): {str(e)}")
                else:
                    logger.error(f"连续 {consecutive_errors} 次网络错误，可能服务不可用")
            except Exception as e:
                # 其他错误
                logger.warning(f"查询任务状态异常: {str(e)}")
                consecutive_errors += 1
            
            # 如果连续错误太多，增加等待时间（指数退避）
            if consecutive_errors > 0:
                wait_time = check_interval * (2 ** min(consecutive_errors - 1, 4))  # 指数退避，最大16倍
                logger.debug(f"连续错误 {consecutive_errors} 次，等待 {wait_time} 秒")
                time.sleep(wait_time)
            else:
                time.sleep(check_interval)
            
            # 检查是否达到最大连续错误
            if consecutive_errors >= max_consecutive_errors * 2:
                error_msg = f"连续 {consecutive_errors} 次查询失败，可能服务不可用"
                logger.error(error_msg)
                return {
                    "file": filename,
                    "task_id": task_id,
                    "status": "connection_error",
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
        
        # 超时
        error_msg = f"任务监控超时: {max_wait}秒 ({max_wait//60}分钟)"
        logger.error(error_msg)
        return {
            "file": filename,
            "task_id": task_id,
            "status": "timeout",
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }
    
    def process_directory(self, directory: Path, force_ocr: bool = True, 
                         max_files: int = None, file_pattern: str = "*.pdf") -> List[Dict[str, Any]]:
        """
        处理目录中的所有PDF文件
        
        Args:
            directory: 目录路径
            force_ocr: 是否强制OCR处理
            max_files: 最大处理文件数（None表示全部）
            file_pattern: 文件匹配模式
            
        Returns:
            List[Dict]: 处理结果列表
        """
        # 查找PDF文件
        pdf_files = list(directory.glob(file_pattern))
        pdf_files.sort()  # 按文件名排序
        
        if max_files:
            pdf_files = pdf_files[:max_files]
        
        total_files = len(pdf_files)
        logger.info(f"找到 {total_files} 个PDF文件，开始处理...")
        
        # 更新统计信息
        self.stats["total"] = total_files
        self.stats["start_time"] = datetime.now().isoformat()
        
        # 串行处理每个文件
        for i, pdf_file in enumerate(pdf_files, 1):
            logger.info(f"处理文件 {i}/{total_files}: {pdf_file.name}")
            
            # 处理PDF文件
            result = self.process_pdf_async(pdf_file, force_ocr)
            self.results.append(result)
            
            # 更新统计
            if result["status"] == "completed":
                self.stats["success"] += 1
            elif result["status"] == "failed":
                self.stats["failed"] += 1
            else:
                self.stats["skipped"] += 1
            
            # 显示进度
            success_rate = (self.stats["success"] / i) * 100
            logger.info(f"进度: {i}/{total_files} | 成功率: {success_rate:.1f}%")
            
            # 文件间等待，减轻后端负荷
            if i < total_files:
                wait_time = 2  # 等待2秒
                logger.debug(f"等待 {wait_time} 秒，减轻后端负荷...")
                time.sleep(wait_time)
        
        # 完成统计
        self.stats["end_time"] = datetime.now().isoformat()
        
        return self.results
    
    def generate_report(self) -> Dict[str, Any]:
        """生成处理报告"""
        if not self.stats["start_time"]:
            return {"error": "尚未开始处理"}
        
        # 计算处理时间
        start_time = datetime.fromisoformat(self.stats["start_time"])
        end_time = datetime.fromisoformat(self.stats["end_time"]) if self.stats["end_time"] else datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 成功率
        success_rate = 0
        if self.stats["total"] > 0:
            success_rate = (self.stats["success"] / self.stats["total"]) * 100
        
        report = {
            "summary": {
                "total_files": self.stats["total"],
                "successful": self.stats["success"],
                "failed": self.stats["failed"],
                "skipped": self.stats["skipped"],
                "success_rate": f"{success_rate:.1f}%",
                "start_time": self.stats["start_time"],
                "end_time": self.stats["end_time"],
                "duration_seconds": duration,
                "duration_minutes": duration / 60
            },
            "details": self.results
        }
        
        return report
    
    def save_report(self, output_file: str = "processing_report.json"):
        """保存处理报告到文件"""
        import json
        
        report = self.generate_report()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"处理报告已保存到: {output_file}")
        return output_file


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="PDF批量处理脚本")
    parser.add_argument("--base-url", default="http://localhost:8001", 
                       help="代理服务URL (默认: http://localhost:8001)")
    parser.add_argument("--auth-token", required=True,
                       help="认证token")
    parser.add_argument("--input-dir", default="../renamed_pdfs",
                       help="输入目录路径 (默认: ../renamed_pdfs)")
    parser.add_argument("--force-ocr", action="store_true", default=True,
                       help="强制OCR处理 (默认: True)")
    parser.add_argument("--max-files", type=int, default=2,
                       help="最大处理文件数 (默认: 2，测试用)")
    parser.add_argument("--output-report", default="processing_report.json",
                       help="输出报告文件 (默认: processing_report.json)")
    
    args = parser.parse_args()
    
    # 验证输入目录
    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"输入目录不存在: {input_dir}")
        sys.exit(1)
    
    # 创建处理器
    processor = PDFBatchProcessor(args.base_url, args.auth_token)
    
    try:
        # 处理PDF文件
        logger.info("=" * 60)
        logger.info("开始批量处理PDF文件")
        logger.info(f"输入目录: {input_dir}")
        logger.info(f"最大文件数: {args.max_files}")
        logger.info(f"强制OCR: {args.force_ocr}")
        logger.info("=" * 60)
        
        results = processor.process_directory(
            directory=input_dir,
            force_ocr=args.force_ocr,
            max_files=args.max_files
        )
        
        # 生成并保存报告
        report = processor.generate_report()
        processor.save_report(args.output_report)
        
        # 打印摘要
        summary = report["summary"]
        logger.info("=" * 60)
        logger.info("处理完成!")
        logger.info(f"总文件数: {summary['total_files']}")
        logger.info(f"成功: {summary['successful']}")
        logger.info(f"失败: {summary['failed']}")
        logger.info(f"跳过: {summary['skipped']}")
        logger.info(f"成功率: {summary['success_rate']}")
        logger.info(f"总耗时: {summary['duration_minutes']:.1f} 分钟")
        logger.info("=" * 60)
        
        # 如果有失败的文件，打印详细信息
        failed_files = [r for r in results if r.get('status') in ['failed', 'timeout']]
        if failed_files:
            logger.warning(f"失败文件 ({len(failed_files)} 个):")
            for failed in failed_files:
                logger.warning(f"  - {failed['file']}: {failed.get('error', '未知错误')}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("用户中断处理")
        # 保存当前进度
        if processor.results:
            processor.save_report("interrupted_report.json")
        return 1
    except Exception as e:
        logger.error(f"处理过程中发生错误: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
