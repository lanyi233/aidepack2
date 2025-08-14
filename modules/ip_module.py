import re
from typing import List, Dict, Tuple
from telethon.events import NewMessage
from urllib.parse import urlparse
from modules.base_module import BaseModule
try:
    import requests
except ImportError:
    import sys
    import subprocess
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "requests"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    import requests

class IPQueryModule(BaseModule):
    def __init__(self):
        super().__init__()
        self.name = "网络信息查询"
        self.description = "查询IP地址或域名的网络信息"
        self.version = "3.0.0"
        self.client = None
        self.api_endpoint = "http://ip-api.com/json/"
        self.timeout = 8
        
        # 健壮的IP匹配正则表达式（支持IPv4和IPv6）
        self.ip_pattern = re.compile(
            r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'  # IPv4
            r'|'  # 或
            r'(?:(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}'  # 标准IPv6
            r'|'  # 或
            r'(?:[0-9a-fA-F]{1,4}:){1,7}:'  # 压缩的IPv6
            r'|'  # 或
            r'(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}'  # 部分压缩的IPv6
            r'|'  # 或
            r':(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}'  # 部分压缩的IPv6
            r'|'  # 或
            r'[0-9a-fA-F]{1,4}::[0-9a-fA-F]{1,4})'  # 双冒号压缩的IPv6
        )
        
        # 域名匹配正则表达式
        self.domain_pattern = re.compile(
            r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]\b',
            re.IGNORECASE
        )

    def get_commands(self) -> Dict[str, str]:
        return {
            "ip": "查询IP/域名信息"
        }

    def get_module_info(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": "网络服务"
        }

    def get_command_usage(self, command: str) -> str:
        return (
            "<blockquote>网络信息查询</blockquote>\n\n"
            "<b>使用方法</b>\n"
            "<code>,ip [IP地址/域名]</code>\n"
        )

    async def module_loaded(self, client) -> None:
        self.client = client

    async def module_unloaded(self) -> None:
        self.client = None

    async def handle_command(self, command: str, event: NewMessage.Event, args: List[str]) -> None:
        if command == "ip":
            await self._handle_ip_query(event, args)

    async def _handle_ip_query(self, event: NewMessage.Event, args: List[str]) -> None:
        # 如果是回复消息模式
        if event.is_reply:
            reply_message = await event.get_reply_message()
            text = reply_message.text or reply_message.raw_text
            
            if not text:
                await event.edit(self.get_command_usage("ip"), parse_mode='html')
                # await event.edit("❌ 被回复的消息没有文本内容", parse_mode='html')
                return
                
            # 提取目标
            targets = self._extract_targets(text)
            if not targets:
                await event.edit(self.get_command_usage("ip"), parse_mode='html')
                # await event.edit("❌ 被回复的消息中未找到IP地址或域名", parse_mode='html')
                return
        # 直接命令模式
        else:
            if not args:
                await event.edit(self.get_command_usage("ip"), parse_mode='html')
                return
                
            # 处理直接输入的目标
            targets = self._process_direct_input(args)
            if not targets:
                await event.edit(self.get_command_usage("ip"), parse_mode='html')
                # await event.edit("❌ 未找到有效的IP地址或域名", parse_mode='html')
                return
        
        # 限制最大处理数量
        if len(targets) > 10:
            targets = targets[:10]
            # await event.edit("只处理前10个目标\n")
        
        # 执行查询
        results = []
        for target in targets:
            try:
                response = requests.get(
                    f"{self.api_endpoint}{target}",
                    params={'lang': 'zh-CN'},
                    timeout=self.timeout
                )
                data = response.json()
                
                if data.get('status') == 'success':
                    results.append(self._format_single_result(data))
                else:
                    error_msg = data.get('message', '查询失败')
                    results.append(f"❌ {target}: {error_msg}")
                    
            except requests.exceptions.Timeout:
                results.append(f"⏳ {target}: 查询超时")
            except Exception as e:
                results.append(f"⚠️ {target}: 查询出错 - {str(e)}")
        
        # 使用blockquote包裹每个结果
        formatted_results = "\n".join([f"<blockquote>{res}</blockquote>" for res in results])
        await event.edit(formatted_results, parse_mode='html')

    def _extract_targets(self, text: str) -> List[str]:
        """从文本中提取所有IP和域名目标"""
        targets = []
        
        # 提取IP地址 (IPv4 和 IPv6)
        targets.extend(match.group() for match in self.ip_pattern.finditer(text))
        
        # 提取域名
        targets.extend(match.group() for match in self.domain_pattern.finditer(text))
        
        # 去重
        unique_targets = []
        for target in targets:
            if target not in unique_targets:
                unique_targets.append(target)
        
        return unique_targets

    def _process_direct_input(self, args: List[str]) -> List[str]:
        """处理直接输入的目标"""
        targets = []
        for arg in args:
            # 处理URL输入
            target = self._clean_target(arg)
            
            # 验证是否是IP或域名
            if self._is_valid_ip(target) or self._is_valid_domain(target):
                targets.append(target)
        
        return targets

    def _clean_target(self, target: str) -> str:
        """清理目标字符串"""
        cleaned = target.strip()
        
        # 处理URL输入
        if cleaned.startswith(('http://', 'https://')):
            try:
                parsed = urlparse(cleaned)
                cleaned = parsed.netloc.split(':')[0]  # 移除端口号
            except:
                pass
        
        return cleaned

    def _is_valid_ip(self, ip: str) -> bool:
        """验证IP地址格式"""
        return bool(self.ip_pattern.fullmatch(ip))

    def _is_valid_domain(self, domain: str) -> bool:
        """验证域名格式"""
        return bool(self.domain_pattern.fullmatch(domain))

    def _format_single_result(self, data: Dict) -> str:
        """格式化单个查询结果"""
        return (
            f"🌐 <b>{data.get('query', '未知目标')}</b>\n"
            f"📍 位置: {data.get('country', '未知')}·{data.get('regionName', '')}·{data.get('city', '')}\n"
            f"🛜 网络: {data.get('isp', '未知')} / {data.get('org', '未知')}\n"
            f"🆔 AS: {data.get('as', '未知')}"
        )
