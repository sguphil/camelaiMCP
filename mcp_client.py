#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP客户端 - 天气查询客户端

这个脚本实现了一个简单的MCP客户端，使用JSON-RPC协议与MCP服务器通信，查询天气信息。
"""

import os
import sys
import json
import logging
import argparse
import subprocess
import time
import signal
import threading
import uuid
from typing import Dict, List, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp-weather-client")

class MCPClient:
    """MCP客户端类，使用JSON-RPC协议与MCP服务器通信"""
    
    def __init__(self, server_command: List[str], verbose: bool = False, timeout: int = 30):
        """
        初始化MCP客户端
        
        Args:
            server_command: 启动MCP服务器的命令
            verbose: 是否显示详细日志
            timeout: 请求超时时间（秒）
        """
        self.server_command = server_command
        self.verbose = verbose
        self.timeout = timeout
        self.process = None
        self.session_id = None
        self.stderr_thread = None
        self.stderr_output = []
        self.request_id = 0
    
    def _log(self, message: str, level: str = "info"):
        """记录日志（如果启用了详细模式）"""
        if self.verbose:
            if level == "debug":
                logger.debug(message)
            elif level == "error":
                logger.error(message)
            else:
                logger.info(message)
    
    def _read_stderr(self):
        """读取服务器的标准错误输出"""
        while self.process and not self.process.poll():
            line = self.process.stderr.readline()
            if line:
                self.stderr_output.append(line.strip())
                self._log(f"服务器错误输出: {line.strip()}", "debug")
    
    def start_server(self):
        """启动MCP服务器进程"""
        self._log(f"启动MCP服务器: {' '.join(self.server_command)}")
        try:
            # 确保没有其他服务器实例在运行
            self.stop_server()
            
            # 启动新的服务器实例
            self.process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            
            # 启动线程读取标准错误输出
            self.stderr_output = []
            self.stderr_thread = threading.Thread(target=self._read_stderr)
            self.stderr_thread.daemon = True
            self.stderr_thread.start()
            
            # 等待服务器启动
            time.sleep(2)
            if self.process.poll() is not None:
                stderr = "\n".join(self.stderr_output)
                raise Exception(f"服务器启动失败: {stderr}")
            
            self._log("服务器启动成功")
        except Exception as e:
            logger.error(f"启动服务器时出错: {str(e)}")
            raise
    
    def stop_server(self):
        """停止MCP服务器进程"""
        if self.process:
            self._log("停止MCP服务器")
            try:
                self.process.terminate()
                # 给进程一些时间来优雅地关闭
                time.sleep(0.5)
                # 如果进程仍在运行，强制终止
                if self.process.poll() is None:
                    self.process.kill()
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"停止服务器时出错: {str(e)}")
            finally:
                self.process = None
                self.stderr_thread = None
    
    def _get_next_request_id(self) -> int:
        """获取下一个请求ID"""
        self.request_id += 1
        return self.request_id
    
    def send_jsonrpc_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        向MCP服务器发送JSON-RPC请求
        
        Args:
            method: 方法名
            params: 参数
        
        Returns:
            服务器响应
        """
        if not self.process:
            self.start_server()
        
        if params is None:
            params = {}
        
        request_id = self._get_next_request_id()
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }
        
        request_json = json.dumps(request)
        self._log(f"发送JSON-RPC请求: {request_json}")
        
        try:
            # 设置超时处理
            def timeout_handler(signum, frame):
                raise TimeoutError("请求超时")
            
            # 注册超时信号处理器
            original_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout)
            
            # 发送请求
            self.process.stdin.write(request_json + "\n")
            self.process.stdin.flush()
            
            # 读取响应
            response_json = self.process.stdout.readline().strip()
            
            # 取消超时
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)
            
            self._log(f"收到JSON-RPC响应: {response_json}")
            
            # 检查服务器是否已退出
            if self.process.poll() is not None:
                stderr = "\n".join(self.stderr_output)
                raise Exception(f"服务器已退出: {stderr}")
            
            # 如果响应为空，可能是服务器没有正确处理请求
            if not response_json:
                stderr = "\n".join(self.stderr_output)
                raise Exception(f"服务器没有返回响应: {stderr}")
            
            try:
                response = json.loads(response_json)
                
                # 检查是否有错误
                if "error" in response:
                    error = response["error"]
                    error_message = error.get("message", "未知错误")
                    error_code = error.get("code", -1)
                    raise Exception(f"JSON-RPC错误: {error_message} (代码: {error_code})")
                
                return response
            except json.JSONDecodeError:
                logger.error(f"无法解析JSON-RPC响应: {response_json}")
                return {"error": {"message": f"无法解析响应: {response_json}", "code": -32700}}
        except TimeoutError as e:
            logger.error(f"JSON-RPC请求超时: {str(e)}")
            stderr = "\n".join(self.stderr_output)
            logger.error(f"服务器错误输出: {stderr}")
            self.stop_server()
            return {"error": {"message": f"请求超时: {str(e)}", "code": -32000}}
        except Exception as e:
            logger.error(f"发送JSON-RPC请求时出错: {str(e)}")
            stderr = "\n".join(self.stderr_output)
            logger.error(f"服务器错误输出: {stderr}")
            self.stop_server()
            return {"error": {"message": f"发送请求时出错: {str(e)}", "code": -32000}}
    
    def create_session(self) -> str:
        """
        创建MCP会话
        
        Returns:
            会话ID
        """
        self._log("创建MCP会话")
        response = self.send_jsonrpc_request("createSession")
        
        if "result" in response and "sessionId" in response["result"]:
            self.session_id = response["result"]["sessionId"]
            self._log(f"会话已创建: {self.session_id}")
            return self.session_id
        else:
            error_msg = response.get("error", {}).get("message", "未知错误")
            logger.error(f"创建会话失败: {error_msg}")
            raise Exception(f"创建会话失败: {error_msg}")
    
    def add_message(self, content: str) -> str:
        """
        向会话添加消息
        
        Args:
            content: 消息内容
        
        Returns:
            消息ID
        """
        if not self.session_id:
            self.create_session()
        
        self._log(f"添加消息: {content}")
        params = {
            "sessionId": self.session_id,
            "message": {
                "role": "user",
                "content": content,
            }
        }
        
        response = self.send_jsonrpc_request("addMessage", params)
        
        if "result" in response and "messageId" in response["result"]:
            message_id = response["result"]["messageId"]
            self._log(f"消息已添加: {message_id}")
            return message_id
        else:
            error_msg = response.get("error", {}).get("message", "未知错误")
            logger.error(f"添加消息失败: {error_msg}")
            raise Exception(f"添加消息失败: {error_msg}")
    
    def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
        
        Returns:
            工具执行结果
        """
        if not self.session_id:
            self.create_session()
        
        self._log(f"调用工具: {tool_name}, 参数: {tool_args}")
        params = {
            "sessionId": self.session_id,
            "name": tool_name,
            "arguments": tool_args
        }
        
        response = self.send_jsonrpc_request("callTool", params)
        
        if "result" in response:
            result = response["result"]
            self._log(f"工具调用结果: {result}")
            return result
        else:
            error_msg = response.get("error", {}).get("message", "未知错误")
            logger.error(f"调用工具失败: {error_msg}")
            raise Exception(f"调用工具失败: {error_msg}")
    
    def get_completion(self, message_id: str) -> str:
        """
        获取消息的完成结果
        
        Args:
            message_id: 消息ID
        
        Returns:
            完成结果
        """
        if not self.session_id:
            self.create_session()
        
        self._log(f"获取完成结果: {message_id}")
        params = {
            "sessionId": self.session_id,
            "messageId": message_id
        }
        
        response = self.send_jsonrpc_request("getCompletion", params)
        
        if "result" in response and "completion" in response["result"]:
            completion = response["result"]["completion"]
            self._log(f"完成结果: {completion}")
            
            # 检查是否有工具调用
            if "toolCall" in completion and completion["toolCall"]:
                tool_call = completion["toolCall"]
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                
                self._log(f"检测到工具调用: {tool_name}")
                tool_result = self.call_tool(tool_name, tool_args)
                
                # 继续获取完成结果
                return self.get_completion(message_id)
            
            # 返回最终结果
            if "content" in completion:
                return completion["content"]
            else:
                return "无内容"
        else:
            error_msg = response.get("error", {}).get("message", "未知错误")
            logger.error(f"获取完成结果失败: {error_msg}")
            raise Exception(f"获取完成结果失败: {error_msg}")
    
    def query_weather(self, query: str) -> str:
        """
        查询天气
        
        Args:
            query: 查询内容
        
        Returns:
            查询结果
        """
        try:
            message_id = self.add_message(query)
            result = self.get_completion(message_id)
            return result
        except Exception as e:
            logger.error(f"查询天气时出错: {str(e)}")
            return f"查询天气时出错: {str(e)}"
        finally:
            self.stop_server()
    
    def direct_query_weather(self, city: str) -> str:
        """
        直接查询城市天气
        
        Args:
            city: 城市名称
        
        Returns:
            天气信息
        """
        try:
            # 创建会话
            self.create_session()
            
            # 直接调用get_weather_by_city工具
            result = self.call_tool("get_weather_by_city", {"city": city})
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"直接查询天气时出错: {str(e)}")
            return f"直接查询天气时出错: {str(e)}"
        finally:
            self.stop_server()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP天气查询客户端")
    parser.add_argument("--query", "-q", type=str, help="天气查询内容")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细日志")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="请求超时时间（秒）")
    parser.add_argument("--direct", "-d", action="store_true", help="直接调用工具而不是使用MCP协议")
    parser.add_argument("--city", "-c", type=str, help="直接指定城市名称")
    args = parser.parse_args()
    
    # 如果指定了城市，则使用城市作为查询内容
    if args.city:
        args.query = args.city
        args.direct = True
    
    if not args.query:
        parser.print_help()
        sys.exit(1)
    
    # MCP服务器命令
    server_command = ["python", "mcp_server.py"]
    
    # 创建MCP客户端
    client = MCPClient(server_command, verbose=args.verbose, timeout=args.timeout)
    
    # 如果使用直接模式，则直接调用工具
    if args.direct:
        result = client.direct_query_weather(args.query)
        print(result)
    else:
        # 查询天气
        result = client.query_weather(args.query)
        print(result)

if __name__ == "__main__":
    main() 