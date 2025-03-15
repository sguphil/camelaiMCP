# MCP 天气查询服务

这是一个基于 Model Context Protocol (MCP) 的天气查询服务，可以获取全球各地的天气信息。

## 功能特点

- 获取指定城市的当前天气
- 获取指定坐标的当前天气
- 获取指定城市的天气预报
- 支持英文地址查询和显示
- 与 Cursor 编辑器集成

## 文件说明

- `mcp_server.py`: MCP 服务器，提供天气查询功能
- `mcp_client.py`: MCP 测试客户端，用于与 MCP 服务器通信


## 安装

### 依赖项

确保已安装以下依赖项：

```bash
pip install -r requirements.txt
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
python mcp_client.py --query "weather for beijing？" --verbose
```



### 在 Cursor 中配置

1. 找到 Cursor 配置MCP servers：
   - 添加command类型MCP Servers，命令为 python /path/to/your/mcp_server.py

4. 在 Cursor 中使用查询天气,只支持英文地址，如beijing， guangzhou，new york...：

```
5 days weather forcast for New York
```

## 支持的查询类型

- 城市天气查询：`beijing今天的天气怎么样？`
- 坐标天气查询：`纬度39.9，经度116.4的天气怎么样？`
- 天气预报查询：`beijing未来3天的天气预报`

## 故障排除

如果遇到问题，请尝试以下步骤：

1. 启动dev模式，测试工具是否正常：
  - uv run --with fastmcp fastmcp dev /mnt/hgfs/sharefolder/camelai2/mcp_server.py

## 许可证

MIT 