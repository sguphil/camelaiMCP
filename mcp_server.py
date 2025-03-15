#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP服务器 - 天气查询服务

这个脚本实现了一个简单的MCP服务器，用于查询天气信息。
使用OpenWeatherMap API获取天气数据。
"""

import os
import sys
import json
import logging
import asyncio
from sys import stdin, stdout
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import httpx
from fastmcp import FastMCP, Context
import mcp.types as types

# 配置标准输入输出编码
stdin.reconfigure(encoding='utf-8')
stdout.reconfigure(encoding='utf-8')

# 加载环境变量
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path)

# 配置日志 - 增加日志级别为DEBUG以获取更多信息
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp-weather-server")

# 获取API密钥
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
if not OPENWEATHERMAP_API_KEY:
    logger.error("未找到OpenWeatherMap API密钥，请在.env文件中设置OPENWEATHERMAP_API_KEY")
    sys.exit(1)

# 初始化MCP服务器 - 添加更多配置选项
mcp = FastMCP(
    name="weather-service",
    instructions="这是一个天气查询服务，可以获取全球各地的天气信息。",
    debug=True  # 启用调试模式
)

# OpenWeatherMap API基础URL
OPENWEATHERMAP_API_BASE = "https://api.openweathermap.org/data/2.5"

async def make_weather_request(url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """向OpenWeatherMap API发送请求并处理响应"""
    params["appid"] = OPENWEATHERMAP_API_KEY
    params["lang"] = "zh_cn"  # 使用中文
    
    logger.debug(f"发送天气API请求: URL={url}, 参数={params}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"天气API响应: {data}")
            return data
        except Exception as e:
            logger.error(f"请求天气API时出错: {str(e)}")
            return None

def format_weather_data(data: Dict[str, Any]) -> str:
    """格式化天气数据为可读字符串"""
    if not data:
        return "无法获取天气数据"
    
    try:
        logger.debug(f"格式化天气数据: {data}")
        weather_desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        if "units" not in data or data.get("units") != "metric":
            temp = temp - 273.15  # 开尔文转摄氏度
        feels_like = data["main"]["feels_like"]
        if "units" not in data or data.get("units") != "metric":
            feels_like = feels_like - 273.15
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        city_name = data["name"]
        country = data["sys"]["country"]
        
        result = f"""
城市: {city_name}, {country}
天气: {weather_desc}
温度: {temp:.1f}°C (体感温度: {feels_like:.1f}°C)
湿度: {humidity}%
风速: {wind_speed} m/s
"""
        logger.debug(f"格式化结果: {result}")
        return result
    except KeyError as e:
        logger.error(f"格式化天气数据时出错: {str(e)}")
        return "天气数据格式错误"

@mcp.tool("get_weather_by_city")
async def get_weather_by_city(ctx: Context, city: str) -> list[types.TextContent]:
    """
    获取指定城市的当前天气
    
    Args:
        city: 城市名称，例如"北京"、"上海"、"New York"
    """
    logger.info(f"查询城市天气: {city}")
    
    url = f"{OPENWEATHERMAP_API_BASE}/weather"
    params = {
        "q": city,
        "units": "metric"
    }
    
    data = await make_weather_request(url, params)
    if data:
        data["units"] = "metric"  # 标记单位为公制
    result = format_weather_data(data)
    logger.info(f"城市天气查询结果: {result}")
    
    return [
        types.TextContent(
            type="text",
            text=result
        )
    ]

@mcp.tool("get_weather_by_coordinates")
async def get_weather_by_coordinates(ctx: Context, latitude: float, longitude: float) -> list[types.TextContent]:
    """
    获取指定坐标的当前天气
    
    Args:
        latitude: 纬度
        longitude: 经度
    """
    logger.info(f"查询坐标天气: 纬度={latitude}, 经度={longitude}")
    
    url = f"{OPENWEATHERMAP_API_BASE}/weather"
    params = {
        "lat": latitude,
        "lon": longitude,
        "units": "metric"
    }
    
    data = await make_weather_request(url, params)
    if data:
        data["units"] = "metric"  # 标记单位为公制
    result = format_weather_data(data)
    logger.info(f"坐标天气查询结果: {result}")
    
    return [
        types.TextContent(
            type="text",
            text=result
        )
    ]

@mcp.tool("get_forecast")
async def get_forecast(ctx: Context, city: str, days: int = 5) -> list[types.TextContent]:
    """
    获取指定城市的天气预报
    
    Args:
        city: 城市名称，例如"北京"、"上海"、"New York"
        days: 预报天数，默认为5天
    """
    logger.info(f"查询城市天气预报: {city}, 天数={days}")
    
    if days < 1 or days > 5:
        return [
            types.TextContent(
                type="text",
                text="预报天数必须在1到5之间"
            )
        ]
    
    url = f"{OPENWEATHERMAP_API_BASE}/forecast"
    params = {
        "q": city,
        "units": "metric",
        "cnt": days * 8  # 每天8个3小时间隔
    }
    
    data = await make_weather_request(url, params)
    if not data:
        return [
            types.TextContent(
                type="text",
                text="无法获取天气预报数据"
            )
        ]
    
    try:
        logger.debug(f"格式化天气预报数据: {data}")
        city_name = data["city"]["name"]
        country = data["city"]["country"]
        forecast_items = data["list"]
        
        # 按天分组预报数据
        daily_forecasts = {}
        for item in forecast_items:
            date = item["dt_txt"].split(" ")[0]
            if date not in daily_forecasts:
                daily_forecasts[date] = []
            daily_forecasts[date].append(item)
        
        # 格式化每天的预报
        result = f"城市: {city_name}, {country}\n\n"
        for date, items in list(daily_forecasts.items())[:days]:
            # 计算每天的平均值
            avg_temp = sum(item["main"]["temp"] for item in items) / len(items)
            descriptions = [item["weather"][0]["description"] for item in items]
            # 获取出现最多的天气描述
            most_common_desc = max(set(descriptions), key=descriptions.count)
            
            result += f"日期: {date}\n"
            result += f"平均温度: {avg_temp:.1f}°C\n"
            result += f"天气: {most_common_desc}\n\n"
        
        logger.info(f"天气预报查询结果: {result}")
        return [
            types.TextContent(
                type="text",
                text=result
            )
        ]
    except KeyError as e:
        logger.error(f"格式化天气预报数据时出错: {str(e)}")
        return [
            types.TextContent(
                type="text",
                text="天气预报数据格式错误"
            )
        ]

@mcp.tool("use_description")
async def list_tools():
    """列出所有可用的工具及其参数"""
    return {
        "tools": [
            {
                "name": "获取城市天气",
                "description": "获取指定城市的当前天气",
                "parameters": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如\"北京\"、\"上海\"、\"New York\"",
                        "required": True
                    }
                }
            },
            {
                "name": "获取坐标天气",
                "description": "获取指定坐标的当前天气",
                "parameters": {
                    "latitude": {
                        "type": "number",
                        "description": "纬度",
                        "required": True
                    },
                    "longitude": {
                        "type": "number",
                        "description": "经度",
                        "required": True
                    }
                }
            },
            {
                "name": "获取天气预报",
                "description": "获取指定城市的天气预报",
                "parameters": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如\"北京\"、\"上海\"、\"New York\"",
                        "required": True
                    },
                    "days": {
                        "type": "number",
                        "description": "预报天数，默认为5天",
                        "required": False
                    }
                }
            }
        ]
    }

@mcp.prompt()
def weather_query_prompt() -> str:
    """提供天气查询的提示模板"""
    return """
当用户询问天气信息时，请考虑以下几点：

1. 如果用户提供了城市名称，使用get_weather_by_city工具获取当前天气
2. 如果用户提供了坐标，使用get_weather_by_coordinates工具获取当前天气
3. 如果用户询问天气预报，使用get_forecast工具获取未来几天的天气预报
4. 如果用户没有明确指定城市或坐标，请询问他们想要查询哪个地区的天气

请以友好的方式回复用户，并提供完整的天气信息。
"""

if __name__ == "__main__":
    logger.info("启动MCP天气服务器...")
    
    # 添加信号处理，确保服务器能够正常关闭
    import signal
    def signal_handler(sig, frame):
        logger.info("接收到终止信号，正在关闭服务器...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行服务器
    try:
        logger.info("开始运行MCP服务器...")
        mcp.run()
    except Exception as e:
        logger.error(f"运行MCP服务器时出错: {str(e)}")
        sys.exit(1) 