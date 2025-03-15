# MCP 天气查询服务

这是一个基于 Model Context Protocol (MCP) 的天气查询服务，可以获取全球各地的天气信息。

## 功能特点

- 获取指定城市的当前天气
- 获取指定坐标的当前天气
- 获取指定城市的天气预报
- 支持中文查询和显示
- 与 Cursor 编辑器集成

## 文件说明

- `mcp_server.py`: MCP 服务器，提供天气查询功能
- `mcp_client.py`: MCP 客户端，用于与 MCP 服务器通信
- `cursor_weather.py`: Cursor 命令行工具，用于在 Cursor 中使用

## 安装

### 依赖项

确保已安装以下依赖项：

```bash
pip install mcp httpx python-dotenv
```

### 配置

1. 在项目根目录创建 `.env` 文件
2. 在 `.env` 文件中添加 OpenWeatherMap API 密钥：

```
OPENWEATHERMAP_API_KEY=your_api_key_here
```

你可以在 [OpenWeatherMap](https://openweathermap.org/api) 注册并获取 API 密钥。

## 使用方法

### 直接使用客户端

```bash
python mcp_client.py --query "北京今天的天气怎么样？" --verbose
```

### 使用 Cursor 命令行工具

```bash
python cursor_weather.py 北京今天的天气怎么样？
```

### 在 Cursor 中配置

1. 找到 Cursor 配置目录：
   - Linux: `~/.cursor/mcp.json`
   - macOS: `~/Library/Application Support/cursor/mcp.json`
   - Windows: `%APPDATA%\cursor\mcp.json`

2. 编辑或创建 `mcp.json` 文件，添加以下内容：

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["/path/to/cursor_weather.py"],
      "env": {
        "OPENWEATHERMAP_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

3. 重启 Cursor

4. 在 Cursor 中使用 `/weather` 命令查询天气：

```
/weather 北京今天的天气怎么样？
```

## 支持的查询类型

- 城市天气查询：`北京今天的天气怎么样？`
- 坐标天气查询：`纬度39.9，经度116.4的天气怎么样？`
- 天气预报查询：`北京未来3天的天气预报`

## 故障排除

如果遇到问题，请尝试以下步骤：

1. 确保 OpenWeatherMap API 密钥正确
2. 检查网络连接
3. 使用 `--verbose` 参数查看详细日志
4. 确保已安装所有依赖项

## 许可证

MIT 