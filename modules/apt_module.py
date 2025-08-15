import json
import os
import re
import shutil
import tempfile
import asyncio
import importlib
import subprocess
from typing import List, Dict, Optional
from telethon.events import NewMessage
from telethon.tl.types import MessageMediaDocument
from modules.base_module import BaseModule

def _install_package(package_name: str):
    try:
        import subprocess
        import importlib
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name])
        importlib.invalidate_caches()
    except subprocess.CalledProcessError:
        raise ImportError(f"Failed to install {package_name}")

try:
    import aiohttp
except ImportError:
    _install_package('aiohttp')
    import aiohttp

PLUGINS_DIR = "./third_party_modules"
SOURCES_FILE = "./third_party_modules/sources.json"

class PluginManagerModule(BaseModule):
    def __init__(self):
        super().__init__()
        self.name = "插件管理器"
        self.description = "管理第三方插件（启用/禁用/安装/上传/列表/删除）"
        self.version = "1.0.0"
        self.client = None

    def get_commands(self) -> Dict[str, str]:
        return {
            "apt": "插件管理"
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
            "<blockquote>插件管理工具</blockquote>\n\n"
            "<b>用法</b>\n"
            "• <code>,apt list</code> 查看插件列表\n"
            "• <code>,apt disable 插件名</code> 禁用插件\n"
            "• <code>,apt enable 插件名</code> 启用插件\n"
            "• <code>,apt install</code> 安装插件\n"
            "• <code>,apt upload 插件名</code> 上传插件文件\n"
            "• <code>,apt remove 插件名</code> 删除插件\n"
            "• <code>,apt update</code> 更新源\n"
            "• <code>,apt search 关键词</code> 搜索插件\n"
            "• <code>,apt source list</code> 查看源列表\n"
            "• <code>,apt source add 源URL</code> 添加新源\n"
            "• <code>,apt source remove 序号</code> 移除源\n"
        )

    async def module_loaded(self, client) -> None:
        self.client = client
        os.makedirs(PLUGINS_DIR, exist_ok=True)
        await self._load_sources()

    async def module_unloaded(self) -> None:
        self.client = None

    async def handle_command(self, command: str, event: NewMessage.Event, args: List[str]) -> None:
        if command == "apt":
            if not args:
                await event.edit(self.get_command_usage("apt"), parse_mode='html')
                return
                
            subcmd = args[0].lower()
            if subcmd == "list":
                await self._list_plugins(event)
            elif subcmd == "disable" and len(args) > 1:
                await self._toggle_plugin(event, args[1], disable=True)
            elif subcmd == "enable" and len(args) > 1:
                await self._toggle_plugin(event, args[1], disable=False)
            elif subcmd == "install" and len(args) > 1:
                await self._install_from_source(event, args[1])
            elif subcmd == "install":
                await self._install_plugin(event)
            elif subcmd == "upload" and len(args) > 1:
                await self._upload_plugin(event, args[1])
            elif subcmd == "remove" and len(args) > 1:
                await self._remove_plugin(event, args[1])
            elif subcmd == "update":
                await self._update_sources(event)
            elif subcmd == "search" and len(args) > 1:
                keyword = " ".join(args[1:])
                await self._search_plugins(event, keyword)
            elif subcmd == "source":
                if len(args) < 2:
                    await event.edit(self.get_command_usage("apt"), parse_mode='html')
                    return
                source_cmd = args[1].lower()
                if source_cmd == "list":
                    await self._list_sources(event)
                elif source_cmd == "add" and len(args) > 2:
                    url = args[2]
                    await self._add_source(event, url)
                elif source_cmd == "remove" and len(args) > 2:
                    try:
                        index = int(args[2])
                        await self._remove_source(event, index)
                    except ValueError:
                        await event.edit("❌ 序号必须是数字", parse_mode='html')
                else:
                    await event.edit(self.get_command_usage("apt"), parse_mode='html')
            else:
                await event.edit(self.get_command_usage("apt"), parse_mode='html')

    async def _list_plugins(self, event: NewMessage.Event) -> None:
        """列出所有插件及其状态（状态在前）"""
        plugins = []
        for filename in os.listdir(PLUGINS_DIR):
            if filename.endswith("_module.py") or filename.endswith("_module.py.disable"):
                # 提取插件名（去除后缀）
                plugin_name = self._get_plugin_name(filename)
                # 状态在前
                status_icon = "🟢" if filename.endswith("_module.py") else "🔴"
                plugins.append(f"{status_icon} {plugin_name}")
        
        if not plugins:
            await event.edit("📦 <b>插件列表</b>\n\n没有找到任何插件", parse_mode='html')
            return
        
        # 按状态分组：启用的在前，禁用的在后
        enabled = [p for p in plugins if p.startswith("🟢")]
        disabled = [p for p in plugins if p.startswith("🔴")]
        enabled.sort()
        disabled.sort()
        
        message = "📦 <b>插件列表</b>\n\n"
        if enabled:
            message += "<b>已启用</b>\n" + "\n".join(enabled) + "\n"
        if disabled:
            message += "<b>已禁用</b>\n" + "\n".join(disabled)
        
        await event.edit(message, parse_mode='html')

    async def _toggle_plugin(self, event: NewMessage.Event, plugin_name: str, disable: bool) -> None:
        """启用或禁用插件"""
        base_name = f"{plugin_name}_module.py"
        enabled_path = os.path.join(PLUGINS_DIR, base_name)
        disabled_path = enabled_path + ".disable"
        
        action = "禁用" if disable else "启用"
        target_path = disabled_path if disable else enabled_path
        source_path = enabled_path if disable else disabled_path
        
        if not os.path.exists(source_path):
            # 检查另一种状态是否存在
            alt_path = disabled_path if not disable else enabled_path
            if os.path.exists(alt_path):
                status = "已禁用" if not disable else "已启用"
                await event.edit(f"⚠️ 插件 <b>{plugin_name}</b> 当前状态为: {status}", parse_mode='html')
                return
            await event.edit(f"❌ 找不到插件: <b>{plugin_name}</b>", parse_mode='html')
            return
        
        try:
            os.rename(source_path, target_path)
            await event.edit(f"✅ 已{action}插件: <b>{plugin_name}</b>", parse_mode='html')
        except Exception as e:
            await event.edit(f"❌ {action}插件失败: {str(e)}", parse_mode='html')

    async def _install_plugin(self, event: NewMessage.Event) -> None:
        """从消息回复中安装插件"""
        reply_msg = await event.get_reply_message()
        if not reply_msg or not reply_msg.media:
            await event.edit("❌ 请回复一个.py插件文件", parse_mode='html')
            return
        
        # 检查是否为文档文件
        if not isinstance(reply_msg.media, MessageMediaDocument):
            await event.edit("❌ 请回复一个.py插件文件", parse_mode='html')
            return
        
        # 获取文件名
        file_name = reply_msg.file.name
        if not file_name or not file_name.endswith("_module.py"):
            await event.edit("❌ 文件名必须以 '_module.py' 结尾", parse_mode='html')
            return
        
        # 下载文件
        plugin_name = self._get_plugin_name(file_name)
        temp_path = os.path.join(PLUGINS_DIR, f"temp_{file_name}")
        final_path = os.path.join(PLUGINS_DIR, file_name)
        
        try:
            # 下载文件
            await event.edit(f"⏬ 正在下载插件: <b>{plugin_name}</b>...", parse_mode='html')
            await reply_msg.download_media(file=temp_path)
            
            # 检查文件内容是否有效
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read(1000)
                if "class" not in content or "BaseModule" not in content:
                    os.remove(temp_path)
                    await event.edit("❌ 无效的插件文件（缺少必要组件）", parse_mode='html')
                    return
            
            # 移动到最终位置（覆盖旧文件）
            os.rename(temp_path, final_path)
            await event.edit(f"✅ 已安装插件: <b>{plugin_name}</b>", parse_mode='html')
        except Exception as e:
            await event.edit(f"❌ 安装失败: {str(e)}", parse_mode='html')
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def _upload_plugin(self, event: NewMessage.Event, plugin_name: str) -> None:
        """上传插件文件（修复文件名问题）"""
        base_name = f"{plugin_name}_module.py"
        enabled_path = os.path.join(PLUGINS_DIR, base_name)
        disabled_path = enabled_path + ".disable"
        
        # 检查文件是否存在
        file_path = None
        is_disabled = False
        
        if os.path.exists(enabled_path):
            file_path = enabled_path
        elif os.path.exists(disabled_path):
            file_path = disabled_path
            is_disabled = True
        else:
            await event.edit(f"❌ 找不到插件: <b>{plugin_name}</b>", parse_mode='html')
            return
        
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as tmp_dir:
                # 确定目标文件名
                target_file = base_name
                
                # 如果是禁用状态，需要重命名文件
                if is_disabled:
                    # 创建临时文件路径
                    temp_path = os.path.join(tmp_dir, base_name)
                    # 复制内容到临时文件
                    shutil.copyfile(file_path, temp_path)
                else:
                    # 直接使用原文件
                    temp_path = file_path
                
                # 上传文件
                await event.edit(f"⏫ 正在上传插件: <b>{plugin_name}</b>...", parse_mode='html')
                await event.reply(f"📦 Tgaide插件: {plugin_name}", file=temp_path)
                
            # 删除上传中的提示消息
            await event.delete()
        except Exception as e:
            await event.edit(f"❌ 上传失败: {str(e)}", parse_mode='html')

    async def _remove_plugin(self, event: NewMessage.Event, plugin_name: str) -> None:
        """删除插件"""
        base_name = f"{plugin_name}_module.py"
        enabled_path = os.path.join(PLUGINS_DIR, base_name)
        disabled_path = enabled_path + ".disable"
        
        # 检查文件是否存在
        found = False
        for path in [enabled_path, disabled_path]:
            if os.path.exists(path):
                found = True
                try:
                    os.remove(path)
                except Exception as e:
                    await event.edit(f"❌ 删除失败: {str(e)}", parse_mode='html')
                    return
        
        if not found:
            await event.edit(f"❌ 找不到插件: <b>{plugin_name}</b>", parse_mode='html')
            return
            
        await event.edit(f"🗑️ 已删除插件: <b>{plugin_name}</b>", parse_mode='html')

    def _get_plugin_name(self, filename: str) -> str:
        """从文件名提取插件名"""
        # 移除后缀
        name = re.sub(r'_module\.py(\.disable)?$', '', filename)
        return name

    async def _load_sources(self):
        """加载源列表"""
        self.sources = []
        if os.path.exists(SOURCES_FILE):
            try:
                with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                    self.sources = json.load(f)
            except:
                pass
    
    async def _save_sources(self):
        """保存源列表"""
        with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.sources, f, indent=2, ensure_ascii=False)

    
    async def _list_sources(self, event: NewMessage.Event) -> None:
        """列出所有源"""
        if not self.sources:
            await event.edit("📡 <b>插件源列表</b>\n\n当前没有添加任何源", parse_mode='html')
            return
        
        message = "📡 <b>插件源列表</b>\n\n"
        for i, source in enumerate(self.sources, 1):
            message += f"{i}: {source.get('name', '未命名源')} ({source.get('id', '未知ID')})\n"
            message += f"   模块数量: {len(source.get('data', []))}\n"
            message += f"   源URL: <code>{source.get('url')}</code>\n\n"
        
        await event.edit(message, parse_mode='html')
    
    async def _add_source(self, event: NewMessage.Event, url: str) -> None:
        """添加新源"""
        # 检查URL是否已存在
        if any(source.get('url') == url for source in self.sources):
            await event.edit("⚠️ 该源已存在", parse_mode='html')
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        await event.edit(f"❌ 下载源信息失败: HTTP {response.status}", parse_mode='html')
                        return
                    
                    # 直接读取文本内容并尝试解析JSON
                    text_content = await response.text()
                    
                    try:
                        source_data = json.loads(text_content)
                    except json.JSONDecodeError:
                        # 尝试从HTML内容中提取JSON
                        match = re.search(r'\{.*\}', text_content, re.DOTALL)
                        if match:
                            try:
                                source_data = json.loads(match.group(0))
                            except json.JSONDecodeError as e:
                                await event.edit(f"❌ 解析源数据失败: {str(e)}", parse_mode='html')
                                return
                        else:
                            await event.edit("❌ 源返回的不是有效的JSON格式", parse_mode='html')
                            return
                    
                    # 验证源格式
                    if not all(key in source_data for key in ['name', 'id', 'data']):
                        await event.edit("❌ 无效的源格式", parse_mode='html')
                        return
        except Exception as e:
            await event.edit(f"❌ 添加源失败: {str(e)}", parse_mode='html')
    
    async def _remove_source(self, event: NewMessage.Event, index: int) -> None:
        """移除源"""
        if index < 1 or index > len(self.sources):
            await event.edit("❌ 无效的序号", parse_mode='html')
            return
        
        removed = self.sources.pop(index - 1)
        await self._save_sources()
        await event.edit(f"🗑️ 已移除源: {removed.get('name', '未命名源')}", parse_mode='html')
    
    async def _find_plugin_in_sources(self, plugin_id: str) -> List[Dict]:
        """在所有源中查找插件"""
        results = []
        for source in self.sources:
            for module in source.get('data', []):
                if module.get('id') == plugin_id:
                    results.append({
                        'source': source,
                        'module': module
                    })
        return results
    
    async def _install_from_source(self, event: NewMessage.Event, plugin_id: str) -> None:
        """从源安装插件"""
        # 检查插件ID格式
        if '/' in plugin_id:
            source_id, plugin_id = plugin_id.split('/', 1)
            # 在指定源中查找
            results = []
            for source in self.sources:
                if source.get('id') == source_id:
                    for module in source.get('data', []):
                        if module.get('id') == plugin_id:
                            results.append({
                                'source': source,
                                'module': module
                            })
        else:
            # 在所有源中查找
            results = await self._find_plugin_in_sources(plugin_id)
        
        if not results:
            await event.edit(f"❌ 未找到插件: {plugin_id}", parse_mode='html')
            return
        
        if len(results) > 1:
            # 处理冲突
            message = "⚠️ 安装冲突\n发现有多个源同时注册了该插件，需指定源进行安装\n\n"
            for result in results:
                source = result['source']
                module = result['module']
                message += f"<code>,apt install {source['id']}/{plugin_id}</code> - {source['name']}/{module['name']}\n"
            
            await event.edit(message, parse_mode='html')
            return
        
        # 只有一个结果，安装插件
        source = results[0]['source']
        module = results[0]['module']
        module_url = module['url']
        
        # 下载插件
        try:
            await event.edit(f"⏬ 正在从源 {source['name']} 下载插件: {module['name']}...", parse_mode='html')
            
            async with aiohttp.ClientSession() as session:
                async with session.get(module_url) as response:
                    if response.status != 200:
                        await event.edit(f"❌ 下载插件失败: HTTP {response.status}", parse_mode='html')
                        return
                    
                    content = await response.text()
                    
                    # 验证内容
                    if "class" not in content or "BaseModule" not in content:
                        await event.edit("❌ 无效的插件文件（缺少必要组件）", parse_mode='html')
                        return
                    
                    # 保存文件
                    filename = f"{plugin_id}_module.py"
                    filepath = os.path.join(PLUGINS_DIR, filename)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    await event.edit(f"✅ 已安装插件: {module['name']} ({plugin_id})", parse_mode='html')
        except Exception as e:
            await event.edit(f"❌ 安装失败: {str(e)}", parse_mode='html')
    
    async def _search_plugins(self, event: NewMessage.Event, keyword: str) -> None:
        """搜索插件"""
        results = []
        
        # 在所有源中搜索
        for source in self.sources:
            for module in source.get('data', []):
                if keyword.lower() in module.get('name', '').lower() or keyword.lower() in module.get('id', '').lower():
                    results.append({
                        'source': source,
                        'module': module
                    })
        
        if not results:
            await event.edit(f"🔍 未找到包含关键词 <b>{keyword}</b> 的插件", parse_mode='html')
            return
        
        message = "🔍 <b>插件搜索结果</b>\n\n"
        
        # 分组显示结果
        grouped = {}
        for result in results:
            source_id = result['source']['id']
            if source_id not in grouped:
                grouped[source_id] = {
                    'source_name': result['source']['name'],
                    'modules': []
                }
            grouped[source_id]['modules'].append(result['module'])
        
        for source_id, data in grouped.items():
            message += f"<b>源: {data['source_name']} ({source_id})</b>\n"
            for module in data['modules']:
                message += f"<blockquote><code>{source_id}/{module['id']}</code> - {module['name']}</blockquote>\n"
            message += "\n"
        
        await event.edit(message, parse_mode='html')

    async def _update_sources(self, event: NewMessage.Event) -> None:
        """更新所有源"""
        if not self.sources:
            await event.edit("📡 没有可更新的源", parse_mode='html')
            return
        
        # 初始化进度消息
        progress_msg = await event.edit("🔄 正在更新源列表...\n\n0% 完成 (0/0)", parse_mode='html')
        
        updated_count = 0
        failed_sources = []
        total = len(self.sources)
        
        try:
            for i, source in enumerate(self.sources):
                # 更新进度
                progress = int((i + 1) / total * 100)
                await progress_msg.edit(
                    f"🔄 正在更新源列表...\n\n{progress}% 完成 ({i+1}/{total})\n"
                    f"当前: {source.get('name', '未命名源')}",
                    parse_mode='html'
                )
                
                # 下载更新源信息
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(source['url']) as response:
                            if response.status != 200:
                                raise Exception(f"HTTP {response.status}")
                            
                            # 直接读取文本内容并尝试解析JSON
                            text_content = await response.text()
                            
                            try:
                                new_source = json.loads(text_content)
                            except json.JSONDecodeError:
                                # 尝试从HTML内容中提取JSON
                                match = re.search(r'\{.*\}', text_content, re.DOTALL)
                                if match:
                                    try:
                                        new_source = json.loads(match.group(0))
                                    except json.JSONDecodeError as e:
                                        raise Exception(f"JSON解析失败: {str(e)}")
                                else:
                                    raise Exception("响应不是有效的JSON格式")
                            
                            # 验证源格式
                            if not all(key in new_source for key in ['name', 'id', 'data']):
                                raise Exception("无效的源格式")
                            
                            # 检查ID是否匹配
                            if new_source['id'] != source['id']:
                                raise Exception(f"源ID不匹配: 本地 {source['id']} ≠ 远程 {new_source['id']}")
                            
                            # 保留原始URL
                            new_source['url'] = source['url']
                            
                            # 更新源
                            self.sources[i] = new_source
                            updated_count += 1
                
                except Exception as e:
                    failed_sources.append({
                        'name': source.get('name', '未命名源'),
                        'reason': str(e)
                    })
            
            # 保存更新后的源列表
            await self._save_sources()
            
            # 生成结果消息
            result_msg = f"✅ 源更新完成\n\n更新成功: {updated_count}/{total}"
            if failed_sources:
                result_msg += "\n\n❌ 更新失败:\n"
                for failed in failed_sources:
                    result_msg += f"• {failed['name']}: {failed['reason']}\n"
            
            await progress_msg.edit(result_msg, parse_mode='html')
        
        except Exception as e:
            await progress_msg.edit(f"❌ 更新过程中发生错误: {str(e)}", parse_mode='html')
