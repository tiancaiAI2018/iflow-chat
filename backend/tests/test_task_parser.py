"""
测试任务解析器服务
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.task_parser import (
    TaskParser,
    ParsedTask,
    parse_task,
    get_task_parser,
)


class TestParsedTask:
    """测试 ParsedTask 数据类"""
    
    def test_parsed_task_creation(self):
        """测试创建 ParsedTask"""
        task = ParsedTask(
            content="查看股票",
            cron_expression="0 9 * * *",
            task_type="daily",
            time_info={"hour": 9, "minute": 0},
            natural_language="每天早上9点提醒我查看股票",
            success=True
        )
        
        assert task.content == "查看股票"
        assert task.cron_expression == "0 9 * * *"
        assert task.task_type == "daily"
        assert task.success is True
        assert task.error is None
    
    def test_parsed_task_with_error(self):
        """测试带错误的 ParsedTask"""
        task = ParsedTask(
            content="",
            cron_expression="",
            task_type="",
            time_info={},
            natural_language="测试",
            success=False,
            error="解析失败"
        )
        
        assert task.success is False
        assert task.error == "解析失败"


class TestTaskParserGenerateCron:
    """测试 Cron 表达式生成"""
    
    def setup_method(self):
        self.parser = TaskParser()
    
    def test_generate_daily_cron(self):
        """测试生成每日 Cron"""
        data = {
            "type": "daily",
            "hour": 9,
            "minute": 30
        }
        cron = self.parser._generate_cron(data)
        assert cron == "30 9 * * *"
    
    def test_generate_daily_cron_default(self):
        """测试每日 Cron 默认值"""
        data = {"type": "daily"}
        cron = self.parser._generate_cron(data)
        assert cron == "0 0 * * *"
    
    def test_generate_weekly_cron(self):
        """测试生成每周 Cron"""
        data = {
            "type": "weekly",
            "hour": 10,
            "minute": 0,
            "weekday": 1  # 周一
        }
        cron = self.parser._generate_cron(data)
        assert cron == "0 10 * * 1"
    
    def test_generate_weekly_cron_default(self):
        """测试每周 Cron 默认值"""
        data = {"type": "weekly", "hour": 9}
        cron = self.parser._generate_cron(data)
        assert cron == "0 9 * * 1"  # 默认周一
    
    def test_generate_weekly_cron_sunday(self):
        """测试每周日 Cron"""
        data = {
            "type": "weekly",
            "hour": 8,
            "minute": 30,
            "weekday": 0  # 周日
        }
        cron = self.parser._generate_cron(data)
        assert cron == "30 8 * * 0"
    
    def test_generate_monthly_cron(self):
        """测试生成每月 Cron"""
        data = {
            "type": "monthly",
            "hour": 9,
            "minute": 0,
            "day_of_month": 15
        }
        cron = self.parser._generate_cron(data)
        assert cron == "0 9 15 * *"
    
    def test_generate_monthly_cron_default(self):
        """测试每月 Cron 默认值"""
        data = {"type": "monthly", "hour": 10}
        cron = self.parser._generate_cron(data)
        assert cron == "0 10 1 * *"  # 默认每月1号
    
    def test_generate_interval_cron_minutes(self):
        """测试生成间隔分钟 Cron"""
        data = {
            "type": "interval",
            "interval_minutes": 30
        }
        cron = self.parser._generate_cron(data)
        assert cron == "*/30 * * * *"
    
    def test_generate_interval_cron_hours(self):
        """测试生成间隔小时 Cron"""
        data = {
            "type": "interval",
            "interval_hours": 2
        }
        cron = self.parser._generate_cron(data)
        assert cron == "0 */2 * * *"
    
    def test_generate_interval_cron_default(self):
        """测试间隔 Cron 默认值"""
        data = {"type": "interval"}
        cron = self.parser._generate_cron(data)
        assert cron == "0 * * * *"  # 默认每小时
    
    def test_generate_once_cron(self):
        """测试生成一次性 Cron"""
        data = {
            "type": "once",
            "hour": 14,
            "minute": 30
        }
        cron = self.parser._generate_cron(data)
        assert cron == "30 14 * * *"
    
    def test_generate_unknown_type_cron(self):
        """测试未知类型默认为每日"""
        data = {
            "type": "unknown",
            "hour": 12,
            "minute": 0
        }
        cron = self.parser._generate_cron(data)
        assert cron == "0 12 * * *"


class TestTaskParserValidateCron:
    """测试 Cron 表达式验证"""
    
    def setup_method(self):
        self.parser = TaskParser()
    
    def test_validate_valid_cron(self):
        """测试验证有效的 Cron"""
        assert self.parser.validate_cron("0 9 * * *") is True
        assert self.parser.validate_cron("30 14 * * 1") is True
        assert self.parser.validate_cron("0 10 15 * *") is True
        assert self.parser.validate_cron("*/15 * * * *") is True
        assert self.parser.validate_cron("0 */2 * * *") is True
    
    def test_validate_invalid_cron_parts(self):
        """测试验证无效的 Cron（部分数量不对）"""
        assert self.parser.validate_cron("0 9 * *") is False  # 少一个部分
        assert self.parser.validate_cron("0 9 * * * *") is False  # 多一个部分
    
    def test_validate_invalid_minute(self):
        """测试验证无效的分钟"""
        assert self.parser.validate_cron("60 9 * * *") is False  # 超出范围
        assert self.parser.validate_cron("-1 9 * * *") is False  # 负数
    
    def test_validate_invalid_hour(self):
        """测试验证无效的小时"""
        assert self.parser.validate_cron("0 24 * * *") is False  # 超出范围
        assert self.parser.validate_cron("0 -1 * * *") is False  # 负数
    
    def test_validate_invalid_day(self):
        """测试验证无效的日期"""
        assert self.parser.validate_cron("0 9 0 * *") is False  # 0 无效
        assert self.parser.validate_cron("0 9 32 * *") is False  # 超出范围
    
    def test_validate_invalid_month(self):
        """测试验证无效的月份"""
        assert self.parser.validate_cron("0 9 1 0 *") is False  # 0 无效
        assert self.parser.validate_cron("0 9 1 13 *") is False  # 超出范围
    
    def test_validate_invalid_weekday(self):
        """测试验证无效的星期"""
        assert self.parser.validate_cron("0 9 * * 7") is False  # 超出范围
        assert self.parser.validate_cron("0 9 * * -1") is False  # 负数
    
    def test_validate_cron_part_star(self):
        """测试验证 * 通配符"""
        assert self.parser._validate_cron_part("*", 0) is True
        assert self.parser._validate_cron_part("*", 1) is True
    
    def test_validate_cron_part_interval(self):
        """测试验证 */n 间隔"""
        assert self.parser._validate_cron_part("*/15", 0) is True  # 每15分钟
        assert self.parser._validate_cron_part("*/60", 0) is False  # 超出范围
        assert self.parser._validate_cron_part("*/0", 0) is False  # 无效
    
    def test_validate_cron_part_number(self):
        """测试验证数字"""
        assert self.parser._validate_cron_part("30", 0) is True  # 有效分钟
        assert self.parser._validate_cron_part("9", 1) is True   # 有效小时
        assert self.parser._validate_cron_part("abc", 0) is False  # 非数字


class TestTaskParserExtractJson:
    """测试 JSON 提取"""
    
    def setup_method(self):
        self.parser = TaskParser()
    
    def test_extract_json_direct(self):
        """测试直接解析 JSON"""
        text = '{"content": "测试", "type": "daily"}'
        result = self.parser._extract_json(text)
        assert result == {"content": "测试", "type": "daily"}
    
    def test_extract_json_from_markdown(self):
        """测试从 Markdown 代码块提取"""
        text = '''这是一个回复：
```json
{"content": "测试", "type": "daily", "hour": 9}
```
'''
        result = self.parser._extract_json(text)
        assert result == {"content": "测试", "type": "daily", "hour": 9}
    
    def test_extract_json_from_text(self):
        """测试从文本中提取 JSON"""
        text = '根据分析，结果如下：{"content": "测试", "type": "daily"}'
        result = self.parser._extract_json(text)
        assert result == {"content": "测试", "type": "daily"}
    
    def test_extract_json_multiple_blocks(self):
        """测试多个 JSON 块（返回第一个有效的）"""
        text = '''```json
{"content": "第一个", "type": "daily"}
```
第二个：
```json
{"content": "第二个", "type": "weekly"}
```
'''
        result = self.parser._extract_json(text)
        assert result is not None
        # 返回第一个有效的 JSON 块
        assert result.get("content") == "第一个"
    
    def test_extract_json_invalid(self):
        """测试无效的 JSON"""
        text = "这不是一个 JSON"
        result = self.parser._extract_json(text)
        assert result is None
    
    def test_extract_json_malformed(self):
        """测试格式错误的 JSON"""
        text = '{"content": "测试", "type": "daily"'  # 缺少闭合括号
        result = self.parser._extract_json(text)
        assert result is None


class TestTaskParserParse:
    """测试解析方法"""
    
    def setup_method(self):
        self.parser = TaskParser()
    
    @pytest.mark.asyncio
    async def test_parse_success(self):
        """测试成功解析"""
        mock_client = AsyncMock()
        mock_client.query.return_value = '''```json
{
    "content": "查看股票",
    "type": "daily",
    "hour": 9,
    "minute": 0
}
```'''
        
        with patch.object(self.parser, '_get_client', return_value=mock_client):
            result = await self.parser.parse("每天早上9点提醒我查看股票")
            
            assert result.success is True
            assert result.content == "查看股票"
            assert result.cron_expression == "0 9 * * *"
            assert result.task_type == "daily"
    
    @pytest.mark.asyncio
    async def test_parse_weekly(self):
        """测试解析每周任务"""
        mock_client = AsyncMock()
        mock_client.query.return_value = '''{
            "content": "发送周报",
            "type": "weekly",
            "hour": 10,
            "minute": 0,
            "weekday": 1
        }'''
        
        with patch.object(self.parser, '_get_client', return_value=mock_client):
            result = await self.parser.parse("每周一上午10点发送周报")
            
            assert result.success is True
            assert result.content == "发送周报"
            assert result.cron_expression == "0 10 * * 1"
            assert result.task_type == "weekly"
    
    @pytest.mark.asyncio
    async def test_parse_interval(self):
        """测试解析间隔任务"""
        mock_client = AsyncMock()
        mock_client.query.return_value = '''{
            "content": "检查服务器状态",
            "type": "interval",
            "interval_minutes": 30
        }'''
        
        with patch.object(self.parser, '_get_client', return_value=mock_client):
            result = await self.parser.parse("每隔30分钟检查一次服务器状态")
            
            assert result.success is True
            assert result.content == "检查服务器状态"
            assert result.cron_expression == "*/30 * * * *"
            assert result.task_type == "interval"
    
    @pytest.mark.asyncio
    async def test_parse_invalid_json_response(self):
        """测试无效 JSON 响应"""
        mock_client = AsyncMock()
        mock_client.query.return_value = "这不是一个有效的 JSON 响应"
        
        with patch.object(self.parser, '_get_client', return_value=mock_client):
            result = await self.parser.parse("测试")
            
            assert result.success is False
            assert result.error == "无法解析任务信息"
    
    @pytest.mark.asyncio
    async def test_parse_exception(self):
        """测试异常处理"""
        mock_client = AsyncMock()
        mock_client.query.side_effect = Exception("连接错误")
        
        with patch.object(self.parser, '_get_client', return_value=mock_client):
            result = await self.parser.parse("测试")
            
            assert result.success is False
            assert "连接错误" in result.error


class TestGetTaskParser:
    """测试获取解析器实例"""
    
    def test_get_task_parser_singleton(self):
        """测试单例模式"""
        parser1 = get_task_parser()
        parser2 = get_task_parser()
        
        assert parser1 is parser2


class TestParseTaskFunction:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_parse_task_function(self):
        """测试便捷函数"""
        mock_client = AsyncMock()
        mock_client.query.return_value = '''{
            "content": "测试任务",
            "type": "daily",
            "hour": 8,
            "minute": 30
        }'''
        
        parser = get_task_parser()
        with patch.object(parser, '_get_client', return_value=mock_client):
            result = await parse_task("每天8点半执行测试任务")
            
            assert result.success is True
            assert result.content == "测试任务"
            assert result.cron_expression == "30 8 * * *"


class TestEdgeCases:
    """边界情况测试"""
    
    def setup_method(self):
        self.parser = TaskParser()
    
    def test_generate_cron_with_none_values(self):
        """测试包含 None 值的数据（None 会被转换为 0）"""
        data = {
            "type": "daily",
            "hour": None,
            "minute": None
        }
        cron = self.parser._generate_cron(data)
        # None 值会被 or 0 转换为 0
        assert cron == "0 0 * * *"
    
    def test_generate_cron_with_empty_dict(self):
        """测试空字典"""
        data = {}
        cron = self.parser._generate_cron(data)
        assert cron == "0 0 * * *"  # 默认每天 0 点
    
    def test_validate_cron_empty_string(self):
        """测试空字符串"""
        assert self.parser.validate_cron("") is False
    
    def test_validate_cron_whitespace(self):
        """测试只有空白"""
        assert self.parser.validate_cron("   ") is False
    
    def test_extract_json_empty_string(self):
        """测试空字符串提取"""
        assert self.parser._extract_json("") is None
    
    def test_extract_json_nested(self):
        """测试嵌套 JSON"""
        text = '{"content": "测试", "time_info": {"hour": 9, "minute": 0}}'
        result = self.parser._extract_json(text)
        assert result["time_info"]["hour"] == 9
    
    @pytest.mark.asyncio
    async def test_parse_empty_string(self):
        """测试解析空字符串"""
        mock_client = AsyncMock()
        mock_client.query.return_value = '{"content": "", "type": "daily"}'
        
        with patch.object(self.parser, '_get_client', return_value=mock_client):
            result = await self.parser.parse("")
            
            # 应该能解析，但内容为空
            assert result.success is True
            assert result.content == ""
