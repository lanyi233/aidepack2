import re
import time
import asyncio
import subprocess
import sys
from typing import List, Dict
from telethon.events import NewMessage
from modules.base_module import BaseModule
from urllib.parse import unquote
from bs4 import BeautifulSoup
import aiohttp

class SubInfoModule(BaseModule):
    def __init__(self):
        super().__init__()
        self.name = "订阅链接信息查询"
        self.description = "识别订阅链接并获取流量信息和机场名称"
        self.version = "1.1.0"
        self.client = None
        self.dependencies_installed = False

    def get_commands(self) -> Dict[str, str]:
        return {
            "subinfo": "查询订阅链接信息"
        }

    def get_module_info(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": "DeepSeek"
        }

    def get_command_usage(self, command: str) -> str:
        return (
            "<blockquote>订阅链接信息查询</blockquote>\n\n"
            "<b>用法</b>\n"
            "• 回复包含订阅链接的消息：<code>,subinfo</code>\n"
            "• 直接使用：<code>,subinfo 订阅链接</code>\n"
            "<b>功能</b>\n"
            "1. 自动识别消息中的订阅链接\n"
            "2. 显示机场名称和流量信息\n"
            "3. 支持多链接同时查询"
        )

    async def module_loaded(self, client) -> None:
        self.client = client
        # 自动安装依赖
        await self._install_dependencies()

    async def module_unloaded(self) -> None:
        self.client = None

    async def _install_dependencies(self):
        """自动安装必要的依赖包"""
        required_packages = ["beautifulsoup4"]
        for package in required_packages:
            try:
                __import__(package)
                print(f"{package} 已安装")
            except ImportError:
                print(f"正在安装 {package}...")
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", package,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    print(f"{package} 安装成功")
                else:
                    print(f"安装失败: {stderr.decode()}")
        
        # 验证依赖是否安装成功
        try:
            __import__("bs4")
            self.dependencies_installed = True
        except ImportError:
            print("依赖安装失败，功能将不可用")

    async def handle_command(self, command: str, event: NewMessage.Event, args: List[str]) -> None:
        if not self.dependencies_installed:
            await event.edit("⚠️ 依赖安装失败，功能不可用。请手动安装：<code>pip install beautifulsoup4</code>", parse_mode='html')
            return
            
        if command == "subinfo":
            await self._handle_subinfo(event, args)

    @staticmethod
    def convert_time_to_str(ts):
        return str(ts).zfill(2)

    @staticmethod
    def sec_to_data(y):
        h = int(y // 3600 % 24)
        d = int(y // 86400)
        h = SubInfoModule.convert_time_to_str(h)
        d = SubInfoModule.convert_time_to_str(d)
        return d + "天" + h + "小时"

    @staticmethod
    def StrOfSize(size):
        def strofsize(integer, remainder, level):
            if integer >= 1024:
                remainder = integer % 1024
                integer //= 1024
                level += 1
                return strofsize(integer, remainder, level)
            elif integer < 0:
                integer = 0
                return strofsize(integer, remainder, level)
            else:
                return integer, remainder, level

        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        integer, remainder, level = strofsize(size, 0, 0)
        if level + 1 > len(units):
            level = -1
        return ('{}.{:>03d} {}'.format(integer, remainder, units[level]))

    async def get_filename_from_url(self, url):
        """获取机场名称"""
        if "sub?target=" in url:
            pattern = r"url=([^&]*)"
            match = re.search(pattern, url)
            if match:
                encoded_url = match.group(1)
                decoded_url = unquote(encoded_url)
                return await self.get_filename_from_url(decoded_url)
        elif "api/v1/client/subscribe?token" in url:
            if "&flag=clash" not in url:
                url += "&flag=clash"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        header = response.headers.get('Content-Disposition', '')
                        pattern = r"filename\*=UTF-8''(.+)"
                        result = re.search(pattern, header)
                        if result:
                            filename = result.group(1)
                            filename = unquote(filename)
                            airport_name = filename.replace("%20", " ").replace("%2B", "+")
                            return airport_name
            except:
                return '未知'
        else:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            try:
                pattern = r'(https?://)([^/]+)'
                match = re.search(pattern, url)
                base_url = match.group(1) + match.group(2) if match else url
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{base_url}/auth/login", headers=headers, timeout=5) as response:
                        if response.status != 200:
                            async with session.get(base_url, headers=headers, timeout=5) as alt_response:
                                html = await alt_response.text()
                        else:
                            html = await response.text()
                        
                        soup = BeautifulSoup(html, 'html.parser')
                        title = soup.title.string if soup.title else "未知"
                        title = str(title).replace('登录 — ', '')
                        
                        if "Attention Required! | Cloudflare" in title:
                            return '该域名仅限国内IP访问'
                        elif "Access denied" in title or "404 Not Found" in title:
                            return '该域名非机场面板域名'
                        elif "Just a moment" in title:
                            return '该域名开启了5s盾'
                        return title
            except:
                return '未知'

    async def _handle_subinfo(self, event: NewMessage.Event, args: List[str]):
        """处理订阅信息查询"""
        try:
            # 获取消息内容
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                message_raw = reply_msg.text or reply_msg.raw_text
            else:
                message_raw = event.text or event.raw_text
            
            if not message_raw:
                await event.edit("❌ 未找到有效消息内容", parse_mode='html')
                return
                
            # 提取URL
            url_list = re.findall(
                r"https?://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|]",
                message_raw
            )
            
            if not url_list:
                await event.edit("❌ 未检测到订阅链接", parse_mode='html')
                return
                
            final_output = ""
            headers = {'User-Agent': 'ClashforWindows/0.18.1'}
            
            for url in url_list:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, timeout=10) as res:
                            # 处理重定向
                            while res.status in (301, 302):
                                redirect_url = res.headers.get('Location')
                                if not redirect_url:
                                    break
                                async with session.get(redirect_url, headers=headers, timeout=10) as new_res:
                                    res = new_res
                            
                            if res.status == 200:
                                info = res.headers.get('subscription-userinfo', '')
                                airport_name = await self.get_filename_from_url(url)
                                
                                if info:
                                    info_num = re.findall(r'\d+', info)
                                    if len(info_num) >= 3:
                                        time_now = int(time.time())
                                        used_up = int(info_num[0])
                                        used_down = int(info_num[1])
                                        total = int(info_num[2])
                                        remaining = total - used_up - used_down
                                        
                                        output_text = (
                                            f"<b>✈️ 机场名称</b>: <code>{airport_name}</code>\n"
                                            f"<b>🔗 订阅链接</b>: <code>{url}</code>\n"
                                            f"<b>⬆️ 已用上行</b>: {self.StrOfSize(used_up)}\n"
                                            f"<b>⬇️ 已用下行</b>: {self.StrOfSize(used_down)}\n"
                                            f"<b>🔄 剩余流量</b>: {self.StrOfSize(remaining)}\n"
                                            f"<b>💾 总流量</b>: {self.StrOfSize(total)}\n"
                                        )
                                        
                                        # 处理过期时间
                                        if len(info_num) >= 4:
                                            expire_time = int(info_num[3])
                                            time_str = time.strftime("%Y-%m-%d", time.localtime(expire_time + 28800))
                                            
                                            if time_now <= expire_time:
                                                last_time = expire_time - time_now
                                                output_text += f"<b>⏳ 有效期至</b>: {time_str} (剩余 {self.sec_to_data(last_time)})\n"
                                            else:
                                                output_text += f"<b>❌ 已过期</b>: {time_str}\n"
                                        else:
                                            output_text += "<b>⏳ 有效期</b>: 未知\n"
                                        
                                        final_output += output_text + "\n"
                                    else:
                                        final_output += f"<b>✈️ 机场名称</b>: {airport_name}\n<b>🔗 链接</b>: <code>{url}</code>\n<b>⚠️ 流量信息格式错误</b>\n\n"
                                else:
                                    final_output += f"<b>✈️ 机场名称</b>: {airport_name}\n<b>🔗 链接</b>: <code>{url}</code>\n<b>ℹ️ 无流量信息</b>\n\n"
                            else:
                                final_output += f"<b>🔗 链接</b>: <code>{url}</code>\n<b>❌ 无法访问 (HTTP {res.status})</b>\n\n"
                except Exception as e:
                    final_output += f"<b>🔗 链接</b>: <code>{url}</code>\n<b>⚠️ 处理错误: {str(e)}</b>\n\n"
            
            await event.edit(final_output if final_output else "❌ 未获取到有效信息", parse_mode='html')
        except Exception as e:
            await event.edit(f"❌ 处理出错: {str(e)}", parse_mode='html')
