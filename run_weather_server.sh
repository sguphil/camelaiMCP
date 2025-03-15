#!/bin/bash

# 运行MCP天气服务器
echo "启动MCP天气服务器..."
uv run --with fastmcp fastmcp run /mnt/hgfs/sharefolder/camelai2/mcp_server.py 