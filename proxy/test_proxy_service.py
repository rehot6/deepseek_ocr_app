import requests
import os
import fitz

def analyze_pdf(pdf_path):
    """分析PDF中的文本、字体和编码信息"""
    print(f"\n📊 分析PDF: {pdf_path}")
    
    try:
        doc = fitz.open(pdf_path)
        print(f"📄 PDF页数: {len(doc)}")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # 提取文本
            text = page.get_text()
            print(f"\n📝 第 {page_num+1} 页文本内容:")
            print(f"   - 文本长度: {len(text)} 字符")
            print(f"   - 文本内容: {repr(text[:200])}...")
            
            # 检查字体信息
            fonts = page.get_fonts()
            print(f"   - 使用的字体数量: {len(fonts)}")
            
            for i, font in enumerate(fonts):
                print(f"     * 字体 {i+1}: 名称={font[3]}, 编码={font[4]}, 类型={font[5]}")
            
            # 检查嵌入的字体
            embedded_fonts = doc.get_page_fonts(page_num)
            print(f"   - 嵌入的字体数量: {len(embedded_fonts)}")
            
            for i, xref in enumerate(embedded_fonts):
                font_info = doc.extract_font(xref[0])
                if font_info:
                    print(f"     * 嵌入字体 {i+1}: {font_info[1]} (类型: {font_info[2]})")
                else:
                    print(f"     * 嵌入字体 {i+1}: 无法提取信息")
        
        doc.close()
        
    except Exception as e:
        print(f"❌ PDF分析失败: {e}")

def test_proxy_service():
    """测试代理服务"""
    
    # 代理服务地址
    proxy_url = "http://localhost:8001"
    
    # 测试文件路径
    test_pdf = "../test/input.pdf"  # 使用现有的测试PDF
    
    if not os.path.exists(test_pdf):
        print(f"❌ 测试文件不存在: {test_pdf}")
        return
    
    print(f"🔍 测试代理服务: {proxy_url}")
    print(f"📄 使用测试文件: {test_pdf}")
    
    # 先分析原始PDF
    analyze_pdf(test_pdf)
    
    try:
        # 上传PDF文件
        with open(test_pdf, 'rb') as f:
            files = {'pdf_file': ('test.pdf', f, 'application/pdf')}
            
            print("\n📤 上传PDF文件...")
            response = requests.post(
                f"{proxy_url}/api/process-pdf",
                files=files,
                timeout=60
            )
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            
            if 'application/json' in content_type:
                # JSON响应 - 无需OCR
                result = response.json()
                print("\n✅ 代理服务响应 (无需OCR):")
                print(f"   - 成功: {result.get('success', False)}")
                print(f"   - 消息: {result.get('message', '')}")
                print(f"   - 需要OCR: {result.get('needs_ocr', False)}")
                
            elif 'application/pdf' in content_type:
                # PDF文件响应 - 已处理OCR
                output_file = "test_proxy_output.pdf"
                with open(output_file, 'wb') as f:
                    f.write(response.content)
                
                print(f"\n✅ 代理服务响应 (已处理OCR):")
                print(f"   - 处理后的PDF已保存: {output_file}")
                print(f"   - 文件大小: {len(response.content)} 字节")
                
                # 分析处理后的PDF
                analyze_pdf(output_file)
                
            else:
                print(f"❌ 未知响应类型: {content_type}")
                print(f"响应内容: {response.text[:200]}...")
                
        else:
            print(f"❌ 代理服务返回错误: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 连接代理服务失败: {e}")
        print("请确保代理服务正在运行: python proxy_service.py")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_proxy_service()
