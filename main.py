import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import akshare as ak
from datetime import datetime, timedelta
from dotenv import load_dotenv
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.types import ModelType

# 加载环境变量
load_dotenv()

# 获取DeepSeek API密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("请在.env文件中设置DEEPSEEK_API_KEY")

# 配置DeepSeek模型 - 使用最新的camel-ai API

# 创建数据分析师agent
def create_analyst_agent():
    """创建一个专门分析股票市场数据的agent"""
    system_message = (
        "你是一位专业的股票市场分析师，擅长分析上证指数数据并提供见解。"
        "你需要分析当天的上证指数表现，包括开盘价、收盘价、最高价、最低价、成交量等指标，"
        "并基于历史数据分析市场趋势，给出未来可能的走势预测。"
        "请提供专业、客观的分析，并给出你的推理过程。"
    )
    # 使用最新版本的camel-ai API初始化ChatAgent
    from camel.models import DeepSeekModel
    from camel.types import ModelType
    model = DeepSeekModel(model_type="deepseek-chat", api_key=DEEPSEEK_API_KEY)
    return ChatAgent(system_message=system_message, model=model)

# 获取上证指数数据
def get_sse_index_data():
    """获取上证指数的历史数据"""
    try:
        # 使用akshare获取上证指数数据
        # 获取最近30天的数据用于分析
        df = ak.stock_zh_index_daily(symbol="sh000001")
        # 确保数据按日期排序
        df = df.sort_index(ascending=False)
        # 获取最近30天的数据
        df = df.head(30)
        return df
    except Exception as e:
        print(f"获取上证指数数据时出错: {e}")
        return None

# 生成数据分析报告
def generate_analysis_report(data):
    """生成上证指数分析报告"""
    if data is None or data.empty:
        return "无法获取上证指数数据，请检查网络连接或API状态。"
    
    # 获取最新一天的数据
    latest_day = data.iloc[0]
    previous_day = data.iloc[1]
    
    # 计算当天涨跌幅
    change_pct = (latest_day['close'] - previous_day['close']) / previous_day['close'] * 100
    
    # 准备分析师需要的数据
    # 将numpy.int64类型的日期转换为字符串格式
    date_str = str(latest_day.name) if isinstance(latest_day.name, (int, np.int64)) else latest_day.name.strftime("%Y-%m-%d")
    analysis_data = {
        "日期": date_str,
        "开盘价": latest_day['open'],
        "收盘价": latest_day['close'],
        "最高价": latest_day['high'],
        "最低价": latest_day['low'],
        "成交量": latest_day['volume'],
        "涨跌幅": f"{change_pct:.2f}%",
        "5日均线": data.head(5)['close'].mean(),
        "10日均线": data.head(10)['close'].mean(),
        "20日均线": data.head(20)['close'].mean(),
        "历史数据": data.head(10).to_dict(orient='records')
    }
    
    return analysis_data

# 可视化上证指数数据
def visualize_sse_index(data):
    """生成上证指数走势图"""
    if data is None or data.empty:
        return None
    
    # 反转数据以便按时间顺序显示
    plot_data = data.iloc[::-1]
    
    # 创建图表
    plt.figure(figsize=(12, 6))
    plt.plot(plot_data.index, plot_data['close'], label='收盘价')
    plt.plot(plot_data.index, plot_data['close'].rolling(window=5).mean(), label='5日均线')
    plt.plot(plot_data.index, plot_data['close'].rolling(window=10).mean(), label='10日均线')
    plt.plot(plot_data.index, plot_data['close'].rolling(window=20).mean(), label='20日均线')
    
    plt.title('上证指数走势图')
    plt.xlabel('日期')
    plt.ylabel('指数值')
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 保存图表
    plt.savefig('sse_index_trend.png')
    plt.close()
    
    return 'sse_index_trend.png'

# 生成Markdown格式的分析报告
def generate_markdown_report(analysis_data, analysis_content, chart_path):
    """生成Markdown格式的分析报告并保存为文件"""
    # 创建Markdown格式的报告
    markdown_report = f"""# 上证指数分析报告

## 基本信息

- **分析日期**: {analysis_data['日期']}
- **开盘价**: {analysis_data['开盘价']}
- **收盘价**: {analysis_data['收盘价']}
- **最高价**: {analysis_data['最高价']}
- **最低价**: {analysis_data['最低价']}
- **成交量**: {analysis_data['成交量']}
- **涨跌幅**: {analysis_data['涨跌幅']}

## 技术指标

- **5日均线**: {analysis_data['5日均线']:.2f}
- **10日均线**: {analysis_data['10日均线']:.2f}
- **20日均线**: {analysis_data['20日均线']:.2f}

## 市场分析

{analysis_content}

## 图表分析

![上证指数走势图]({chart_path})

---
*本报告由AI分析师生成，仅供参考，不构成投资建议*
"""
    
    # 保存为Markdown文件
    report_filename = f"上证指数分析报告_{analysis_data['日期']}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    
    return report_filename

# 主函数
def main():
    print("正在获取上证指数数据...")
    sse_data = get_sse_index_data()
    
    if sse_data is not None:
        print("数据获取成功，正在生成分析报告...")
        analysis_data = generate_analysis_report(sse_data)
        
        # 创建分析师agent
        analyst = create_analyst_agent()
        
        # 准备提问
        prompt = f"""
        请分析以下上证指数数据，并给出当前市场状况和未来可能的走势预测：
        
        日期: {analysis_data['日期']}
        开盘价: {analysis_data['开盘价']}
        收盘价: {analysis_data['收盘价']}
        最高价: {analysis_data['最高价']}
        最低价: {analysis_data['最低价']}
        成交量: {analysis_data['成交量']}
        涨跌幅: {analysis_data['涨跌幅']}
        5日均线: {analysis_data['5日均线']}
        10日均线: {analysis_data['10日均线']}
        20日均线: {analysis_data['20日均线']}
        
        请提供详细分析，包括：
        1. 当天市场表现分析
        2. 技术指标分析（如均线、成交量等）
        3. 市场趋势判断
        4. 未来可能的走势预测
        5. 投资建议
        
        请使用Markdown格式输出，使用标题、列表和强调等Markdown语法使内容更加结构化和易于阅读。
        """
        
        # 发送消息给分析师agent
        user_message = BaseMessage(role_name="User", role_type="user", meta_dict={}, content=prompt)
        analyst_response = analyst.step(user_message)
        
        # 生成可视化图表
        chart_path = visualize_sse_index(sse_data)
        
        # 提取分析内容
        analysis_content = ""
        try:
            # 从响应中提取消息内容
            response_str = str(analyst_response)
            if 'content=' in response_str:
                # 提取content部分
                content_start = response_str.find('content=') + 9  # 'content=' 长度为8，加上引号
                content_end = response_str.find("', video_bytes=") if "', video_bytes=" in response_str else response_str.find("', image_list=")
                if content_end > content_start:
                    analysis_content = response_str[content_start:content_end]
                else:
                    analysis_content = "无法解析分析内容，显示原始响应：\n" + response_str
            else:
                analysis_content = response_str
        except Exception as e:
            analysis_content = f"无法获取分析结果: {e}\n响应对象类型: {type(analyst_response)}"
        
        # 生成Markdown报告并保存
        report_file = generate_markdown_report(analysis_data, analysis_content, chart_path)
        
        # 在控制台显示报告已生成的消息
        print(f"\n===== 上证指数分析报告已生成 =====\n")
        print(f"报告已保存至: {report_file}")
        print(f"图表已保存至: {chart_path}")
        
        # 在控制台显示报告内容预览
        print("\n报告内容预览:\n")
        print(f"# 上证指数分析报告 - {analysis_data['日期']}")
        print(f"\n涨跌幅: {analysis_data['涨跌幅']}")
        print("\n(完整报告请查看生成的Markdown文件)")
    else:
        print("获取数据失败，请检查网络连接或API状态。")

if __name__ == "__main__":
    main()