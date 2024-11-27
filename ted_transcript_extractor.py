import requests
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os
import subprocess

class TEDTranscriptGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TED字幕提取器")
        self.root.geometry("600x400")
        
        # 保存最近导出的文件路径
        self.last_saved_file = None
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # URL输入框
        ttk.Label(main_frame, text="请输入TED演讲URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=50)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 复选框控制是否导出中文字幕
        self.include_chinese = tk.BooleanVar(value=True)
        self.chinese_checkbox = ttk.Checkbutton(
            main_frame, 
            text="导出中文字幕（如果有）", 
            variable=self.include_chinese
        )
        self.chinese_checkbox.grid(row=2, column=0, sticky=tk.W, pady=5)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 提取按钮
        self.extract_button = ttk.Button(button_frame, text="提取字幕", command=self.start_extraction)
        self.extract_button.pack(side=tk.LEFT, padx=5)
        
        # 打开目录按钮（初始状态为禁用）
        self.open_folder_button = ttk.Button(
            button_frame, 
            text="打开文件位置", 
            command=self.open_file_location,
            state='disabled'
        )
        self.open_folder_button.pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress_var = tk.StringVar(value="就绪")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=4, column=0, sticky=tk.W, pady=5)
        
        # 日志文本框
        self.log_text = tk.Text(main_frame, height=15, width=50)
        self.log_text.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=5, column=2, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set

    def open_file_location(self):
        """打开文件所在目录"""
        if self.last_saved_file and os.path.exists(self.last_saved_file):
            # Windows
            if sys.platform == 'win32':
                subprocess.run(['explorer', '/select,', os.path.abspath(self.last_saved_file)])
            # macOS
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', self.last_saved_file])
            # Linux
            else:
                subprocess.run(['xdg-open', os.path.dirname(self.last_saved_file)])
        else:
            messagebox.showwarning("警告", "找不到最近保存的文件")

    def save_transcript(self, content, video_id):
        """保存内容到文件"""
        output_file = f"{video_id}.md"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.last_saved_file = os.path.abspath(output_file)
            self.open_folder_button.state(['!disabled'])  # 启用打开目录按钮
            self.log(f"成功保存字幕到：{output_file}")
            return True
        except Exception as e:
            self.log(f"保存文件时出错: {str(e)}")
            return False

    def start_extraction(self):
        self.extract_button.state(['disabled'])
        self.open_folder_button.state(['disabled'])  # 开始新的提取时禁用按钮
        self.progress_var.set("正在处理...")
        self.log_text.delete(1.0, tk.END)
        
        thread = threading.Thread(target=self.extract_transcript)
        thread.daemon = True
        thread.start()

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        
    def extract_transcript(self):
        try:
            url = self.url_var.get().strip()
            if not url:
                raise ValueError("请输入URL")
                
            self.log(f"正在处理URL: {url}")
            
            # 提取video_id
            video_id = self.extract_video_id(url)
            self.log(f"提取到的video_id: {video_id}")
            
            # 获取英文字幕
            en_paragraphs, en_success = self.get_ted_transcript(video_id, "en")
            if not en_success:
                raise ValueError("获取英文字幕失败")
            
            content = None
            
            # 根据复选框状态决定是否获取中文字幕
            if self.include_chinese.get():
                # 获取中文字幕
                zh_paragraphs, zh_success = self.get_ted_transcript(video_id, "zh-cn")
                
                if zh_success:
                    self.log("找到中文字幕，生成双语字幕...")
                    content = self.generate_bilingual_markdown(video_id, en_paragraphs, zh_paragraphs)
                else:
                    self.log("未找到中文字幕，仅生成英文字幕...")
                    content = self.generate_english_markdown(video_id, en_paragraphs)
            else:
                self.log("仅生成英文字幕...")
                content = self.generate_english_markdown(video_id, en_paragraphs)
            
            if content:
                if self.save_transcript(content, video_id):
                    self.log("字幕提取完成！")
            else:
                raise ValueError("生成字幕内容失败")
                
        except Exception as e:
            self.log(f"错误: {str(e)}")
            messagebox.showerror("错误", str(e))
        finally:
            self.extract_button.state(['!disabled'])
            self.progress_var.set("就绪")

    def generate_english_markdown(self, video_id, en_paragraphs):
        """仅生成英文字幕的Markdown内容"""
        markdown_content = [f"# TED Talk: {video_id}\n\n"]
        
        for para in en_paragraphs:
            text = ' '.join(cue['text'].replace("\n", " ").strip() 
                           for cue in para['cues'])
            if text in ["(Laughter)", "(Applause)"]:
                markdown_content.append(f"\n*{text}*\n\n")
            else:
                markdown_content.append(f"{text}\n\n")
        
        markdown_content.append("\n---\n*Source: TED Talk Transcript*")
        return ''.join(markdown_content)

    # 这里添加之前的所有辅助方法（extract_video_id, get_ted_transcript等）
    # 只需要修改print语句为self.log()
    
    def extract_video_id(self, url):
        """从TED视频URL中提取video_id"""
        patterns = [
            r'talks/([^/\?]+)',
            r'talks/([^/\?]+)/transcript',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError("无法从URL中提取video_id")

    def get_ted_transcript(self, video_id, language="en"):
        """获取指定语言的字幕"""
        query = """
        query {
          translation(
            videoId: "%s"
            language: "%s"
          ) {
            paragraphs {
              cues {
                text
                time
              }
            }
          }
        }
        """ % (video_id, language)

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        try:
            response = requests.post(
                'https://www.ted.com/graphql',
                json={'query': query},
                headers=headers
            )
            
            response.raise_for_status()
            data = response.json()
            
            if 'errors' in data:
                raise ValueError(f"GraphQL错误: {data['errors']}")
                
            if not data.get('data', {}).get('translation', {}).get('paragraphs'):
                return None, False

            return data['data']['translation']['paragraphs'], True
            
        except Exception as e:
            self.log(f"获取{language}字幕时出错: {str(e)}")
            return None, False

    def generate_bilingual_markdown(self, video_id, en_paragraphs, zh_paragraphs):
        """生成双语字幕的Markdown内容"""
        markdown_content = [f"# TED Talk: {video_id}\n\n"]
        
        if len(en_paragraphs) != len(zh_paragraphs):
            self.log("警告：英文和中文字幕段落数不匹配")
            return None
        
        for en_para, zh_para in zip(en_paragraphs, zh_paragraphs):
            para_content = []
            
            en_text = ' '.join(cue['text'].replace("\n", " ").strip() 
                              for cue in en_para['cues'])
            if en_text in ["(Laughter)", "(Applause)"]:
                para_content.append(f"\n*{en_text}*\n")
            else:
                para_content.append(f"{en_text}\n")
            
            zh_text = ' '.join(cue['text'].replace("\n", " ").strip() 
                              for cue in zh_para['cues'])
            if zh_text not in ["(Laughter)", "(Applause)"]:
                para_content.append(f"*{zh_text}*\n\n")
            
            markdown_content.extend(para_content)
        
        markdown_content.append("\n---\n*Source: TED Talk Transcript*")
        return ''.join(markdown_content)

if __name__ == "__main__":
    root = tk.Tk()
    app = TEDTranscriptGUI(root)
    root.mainloop() 