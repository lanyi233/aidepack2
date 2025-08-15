import asyncio
import subprocess
from typing import List, Dict
from telethon.events import NewMessage
from modules.base_module import BaseModule

class ShellModule(BaseModule):
    def __init__(self):
        super().__init__()
        self.name = "Shell执行器"
        self.description = "执行Shell命令并实时显示输出"
        self.version = "1.0.0"
        self.client = None
        self.active_processes = {}  # 跟踪正在运行的进程

    def get_commands(self) -> Dict[str, str]:
        return {
            "sh": "执行Shell命令"
        }

    def get_module_info(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": "lanyi233"
        }

    def get_command_usage(self, command: str) -> str:
        usage_map = {
            "sh": (
                "<blockquote>执行Shell命令</blockquote>\n\n"
                "<b>用法</b>\n"
                "• <code>,sh 命令</code> 执行Shell命令"
            )
        }
        return usage_map.get(command, "")

    async def module_loaded(self, client) -> None:
        self.client = client

    async def module_unloaded(self) -> None:
        # 取消所有正在运行的进程
        for task in self.active_processes.values():
            task.cancel()
        self.client = None

    async def handle_command(self, command: str, event: NewMessage.Event, args: List[str]) -> None:
        if command == "sh":
            await self._handle_shell(event, args)

    async def _handle_shell(self, event: NewMessage.Event, args: List[str]) -> None:
        # 安全校验
        if not args:
            await event.edit(self.get_command_usage("sh"), parse_mode='html')
            return
            
        command = " ".join(args)
        
        # 安全过滤 - 禁止危险命令
        blocked_commands = ["yuanshenqidong"]
        if any(cmd in command for cmd in blocked_commands):
            await event.edit("❌ 拒绝执行危险命令", parse_mode='html')
            return
        
        # 创建初始消息
        progress_msg = await event.edit(
            f"✨运行中... [<code>{command}</code>]\n<blockquote>等待输出...</blockquote>",
            parse_mode='html'
        )
        
        # 创建任务ID
        task_id = f"{event.chat_id}_{event.id}"
        
        # 启动任务
        task = asyncio.create_task(self._execute_shell(event, command, task_id))
        self.active_processes[task_id] = task
        
        try:
            await task
        except asyncio.CancelledError:
            await event.edit(f"⛔ 命令已取消 [<code>{command}</code>]", parse_mode='html')
        finally:
            self.active_processes.pop(task_id, None)

    async def _execute_shell(self, event: NewMessage.Event, command: str, task_id: str) -> None:
        """执行Shell命令并实时更新消息"""
        try:
            # 创建子进程
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                limit=1024  # 输出缓冲区大小
            )
            
            output = ""
            last_update = asyncio.get_event_loop().time()
            
            # 实时读取输出
            while True:
                # 读取stdout和stderr
                stdout = await process.stdout.read(256)
                stderr = await process.stderr.read(256)
                
                # 处理输出
                if stdout:
                    output += stdout.decode('utf-8', 'ignore')
                if stderr:
                    output += stderr.decode('utf-8', 'ignore')
                
                # 定期更新消息 (每秒最多更新一次)
                current_time = asyncio.get_event_loop().time()
                if output and (current_time - last_update > 1.0):
                    truncated = self._truncate_output(output)
                    await event.edit(
                        f"✨运行中... [<code>{command}</code>]\n<blockquote>{truncated}</blockquote>",
                        parse_mode='html'
                    )
                    last_update = current_time
                
                # 检查进程是否结束
                if process.stdout.at_eof() and process.stderr.at_eof():
                    await process.wait()
                    break
                    
            # 最终输出
            exit_code = process.returncode
            truncated = self._truncate_output(output)
            status = "✅" if exit_code == 0 else "⚠️"
            
            await event.edit(
                f"{status}运行完成 [<code>{command}</code>] (Code: {exit_code})\n<blockquote>{truncated}</blockquote>",
                parse_mode='html'
            )
            
        except asyncio.TimeoutError:
            await event.edit(f"⏱️ 命令超时 [<code>{command}</code>]", parse_mode='html')
        except Exception as e:
            await event.edit(f"❌ 执行错误: {str(e)} [<code>{command}</code>]", parse_mode='html')

    def _truncate_output(self, output: str, max_length: int = 2000) -> str:
       """改进的截断输出函数"""
       if len(output) <= max_length:
           return output
       
       # 尝试寻找自然断点进行截断
       half = max_length // 2
       first_half = output[:half]
       second_half = output[-half:]
       
       # 在第一半中寻找最后一个换行符
       last_nl = first_half.rfind('\n')
       if last_nl > half - 100:  # 在末尾100字符内找到换行符
           first_half = first_half[:last_nl]
       
       # 在第二半中寻找第一个换行符
       first_nl = second_half.find('\n')
       if first_nl < 100 and first_nl != -1:  # 在开头100字符内找到换行符
           second_half = second_half[first_nl+1:]
       
       return (
           first_half + 
           "\n\n-----截断-----\n\n" + 
           second_half
       )
