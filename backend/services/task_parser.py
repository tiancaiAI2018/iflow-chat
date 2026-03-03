"""
自然语言任务解析服务
使用 iFlow 解析用户意图，提取时间信息和任务内容，生成 Cron 表达式
"""
import json
import re
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime

from backend.services.iflow_client import IFlowClientService, get_iflow_client


@dataclass
class ParsedTask:
    """解析后的任务数据结构"""
    content: str                    # 任务内容描述
    cron_expression: str            # Cron 表达式
    task_type: str                  # 任务类型: daily, weekly, monthly, once, interval
    time_info: dict                 # 时间信息
    natural_language: str           # 原始自然语言描述
    success: bool = True            # 解析是否成功
    error: Optional[str] = None     # 错误信息


# 系统提示词，用于指导 iFlow 解析任务
PARSE_PROMPT = """你是一个定时任务解析助手。请分析用户的自然语言描述，提取以下信息：

1. 任务内容：用户想要执行什么任务（提取核心动作和目标）
2. 时间类型：daily（每天）、weekly（每周）、monthly（每月）、once（一次）、interval（间隔）
3. 具体时间：小时、分钟、星期几（如果是weekly）、日期（如果是monthly）
4. 间隔周期：如果是 interval 类型，提取间隔分钟数或小时数

请严格按照以下 JSON 格式返回结果，不要添加任何其他内容：

```json
{
    "content": "任务内容描述",
    "type": "daily|weekly|monthly|once|interval",
    "hour": 小时数（0-23），
    "minute": 分钟数（0-59），
    "weekday": 星期几（0-6，0=周日，仅weekly需要），
    "day_of_month": 日期（1-31，仅monthly需要），
    "interval_minutes": 间隔分钟数（仅interval需要），
    "interval_hours": 间隔小时数（仅interval需要）
}
```

示例：
用户输入："每天早上9点提醒我查看股票"
返回：
```json
{
    "content": "提醒我查看股票",
    "type": "daily",
    "hour": 9,
    "minute": 0
}
```

用户输入："每周一上午10点发送周报"
返回：
```json
{
    "content": "发送周报",
    "type": "weekly",
    "hour": 10,
    "minute": 0,
    "weekday": 1
}
```

用户输入："每隔30分钟检查一次服务器状态"
返回：
```json
{
    "content": "检查服务器状态",
    "type": "interval",
    "interval_minutes": 30
}
```

现在请解析以下用户输入："""


class TaskParser:
    """自然语言任务解析器"""
    
    def __init__(self):
        self._client: Optional[IFlowClientService] = None
    
    async def _get_client(self) -> IFlowClientService:
        """获取 iFlow 客户端"""
        if self._client is None:
            self._client = await get_iflow_client()
        return self._client
    
    async def parse(self, natural_language: str) -> ParsedTask:
        """
        解析自然语言任务描述
        
        Args:
            natural_language: 自然语言描述
        
        Returns:
            ParsedTask: 解析结果
        """
        try:
            # 调用 iFlow 解析
            client = await self._get_client()
            
            # 构建提示词
            prompt = f"{PARSE_PROMPT}\n\"{natural_language}\""
            
            # 获取响应
            response = await client.query(prompt)
            
            # 解析 JSON 响应
            parsed_data = self._extract_json(response)
            
            if not parsed_data:
                return ParsedTask(
                    content="",
                    cron_expression="",
                    task_type="",
                    time_info={},
                    natural_language=natural_language,
                    success=False,
                    error="无法解析任务信息"
                )
            
            # 生成 Cron 表达式
            cron_expression = self._generate_cron(parsed_data)
            
            # 构建返回结果
            return ParsedTask(
                content=parsed_data.get('content', ''),
                cron_expression=cron_expression,
                task_type=parsed_data.get('type', 'daily'),
                time_info=parsed_data,
                natural_language=natural_language,
                success=True
            )
            
        except Exception as e:
            return ParsedTask(
                content="",
                cron_expression="",
                task_type="",
                time_info={},
                natural_language=natural_language,
                success=False,
                error=f"解析失败: {str(e)}"
            )
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """
        从文本中提取 JSON 对象
        
        Args:
            text: 包含 JSON 的文本
        
        Returns:
            dict: 解析后的字典，失败返回 None
        """
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 块中的内容
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # 尝试提取 { ... } 块
        brace_pattern = r'\{[\s\S]*\}'
        matches = re.findall(brace_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _generate_cron(self, data: dict) -> str:
        """
        根据解析数据生成 Cron 表达式
        
        Cron 格式: 分钟 小时 日 月 星期
        
        Args:
            data: 解析后的数据字典
        
        Returns:
            str: Cron 表达式
        """
        task_type = data.get('type', 'daily')
        # 处理 None 值，使用默认值 0
        hour = data.get('hour') or 0
        minute = data.get('minute') or 0
        weekday = data.get('weekday')  # 0-6, 0=Sunday
        day_of_month = data.get('day_of_month')  # 1-31
        interval_minutes = data.get('interval_minutes')
        interval_hours = data.get('interval_hours')
        
        if task_type == 'daily':
            # 每天: 0 9 * * *
            return f"{minute} {hour} * * *"
        
        elif task_type == 'weekly':
            # 每周: 0 9 * * 1 (每周一)
            if weekday is None:
                weekday = 1  # 默认周一
            return f"{minute} {hour} * * {weekday}"
        
        elif task_type == 'monthly':
            # 每月: 0 9 1 * * (每月1号)
            if day_of_month is None:
                day_of_month = 1  # 默认每月1号
            return f"{minute} {hour} {day_of_month} * *"
        
        elif task_type == 'once':
            # 一次性任务：使用具体日期时间
            # 这里简化为当天指定时间执行
            return f"{minute} {hour} * * *"
        
        elif task_type == 'interval':
            # 间隔任务
            if interval_hours:
                # 每N小时: 0 */N * * *
                return f"0 */{interval_hours} * * *"
            elif interval_minutes:
                # 每N分钟: */N * * * *
                return f"*/{interval_minutes} * * * *"
            else:
                # 默认每小时
                return "0 * * * *"
        
        else:
            # 未知类型，默认每天
            return f"{minute} {hour} * * *"
    
    def validate_cron(self, cron_expression: str) -> bool:
        """
        验证 Cron 表达式是否有效
        
        Args:
            cron_expression: Cron 表达式
        
        Returns:
            bool: 是否有效
        """
        try:
            parts = cron_expression.split()
            if len(parts) != 5:
                return False
            
            # 检查每个部分是否有效
            for i, part in enumerate(parts):
                if not self._validate_cron_part(part, i):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_cron_part(self, part: str, position: int) -> bool:
        """
        验证 Cron 表达式的单个部分
        
        Args:
            part: 部分（分钟、小时、日、月、星期）
            position: 位置索引
        
        Returns:
            bool: 是否有效
        """
        # 定义每个位置的有效范围
        ranges = [
            (0, 59),   # 分钟
            (0, 23),   # 小时
            (1, 31),   # 日
            (1, 12),   # 月
            (0, 6),    # 星期
        ]
        
        min_val, max_val = ranges[position]
        
        # 处理 * 和 */n 格式
        if part == '*':
            return True
        
        if part.startswith('*/'):
            try:
                interval = int(part[2:])
                return 1 <= interval <= max_val
            except ValueError:
                return False
        
        # 处理数字
        try:
            value = int(part)
            return min_val <= value <= max_val
        except ValueError:
            return False


# 全局解析器实例
_parser: Optional[TaskParser] = None


def get_task_parser() -> TaskParser:
    """获取任务解析器单例"""
    global _parser
    if _parser is None:
        _parser = TaskParser()
    return _parser


async def parse_task(natural_language: str) -> ParsedTask:
    """
    解析自然语言任务（便捷函数）
    
    Args:
        natural_language: 自然语言描述
    
    Returns:
        ParsedTask: 解析结果
    """
    parser = get_task_parser()
    return await parser.parse(natural_language)
