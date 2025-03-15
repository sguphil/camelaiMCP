#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
直接使用OpenWeatherMap API查询天气的测试脚本
"""

import os
import sys
import json
import requests
import argparse

# OpenWeatherMap API密钥
API_KEY = "d62a4cc10e0867c836827794528c31a7"

def get_weather(city: str):
    """
    获取指定城市的天气
    
    Args:
        city: 城市名称
    """
    print(f"查询城市天气: {city}")
    
    # 构建API请求URL
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "units": "metric",
        "lang": "zh_cn",
        "appid": API_KEY
    }
    
    try:
        # 发送请求
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        
        # 格式化天气数据
        weather_desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        city_name = data["name"]
        country = data["sys"]["country"]
        
        # 输出结果
        result = f"""
城市: {city_name}, {country}
天气: {weather_desc}
温度: {temp:.1f}°C (体感温度: {feels_like:.1f}°C)
湿度: {humidity}%
风速: {wind_speed} m/s
"""
        print(result)
        
    except Exception as e:
        print(f"查询天气时出错: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="直接使用OpenWeatherMap API查询天气")
    parser.add_argument("city", type=str, help="城市名称")
    args = parser.parse_args()
    
    get_weather(args.city)

if __name__ == "__main__":
    main() 