#!/bin/bash

# 运行MCP天气客户端
echo "启动MCP天气客户端..."

# 获取城市参数
CITY=${1:-"北京"}
echo "查询城市: $CITY"

# 运行客户端
python mcp_client.py --city "$CITY" --verbose --timeout 60 