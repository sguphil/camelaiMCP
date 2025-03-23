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
import argparse
import time
import requests
from requests.exceptions import RequestException
from urllib3.exceptions import HTTPError
import matplotlib as mpl
from matplotlib.font_manager import FontProperties

# 配置中文字体支持
def configure_chinese_font():
    """配置matplotlib以使用英文字体并避免中文乱码问题"""
    # 强制使用英文标签
    global USE_ENGLISH_LABELS
    USE_ENGLISH_LABELS = True
    
    # 设置基本英文字体
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    
    print("已配置为完全使用英文标签，避免中文字体问题")

# 调用字体配置函数
USE_ENGLISH_LABELS = True  # 初始值，强制使用英文
configure_chinese_font()

# 最大重试次数
MAX_RETRIES = 3
# 重试间隔（秒）
RETRY_DELAY = 2
# 是否使用英文标签（当找不到中文字体时）
USE_ENGLISH_LABELS = False  # 初始值，会在configure_chinese_font中根据情况修改

# 加载环境变量
load_dotenv()

# 获取DeepSeek API密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("请在.env文件中设置DEEPSEEK_API_KEY")

# 配置DeepSeek模型 - 使用最新的camel-ai API

# 创建数据分析师agent
def create_analyst_agent(stock_name="上证指数"):
    """创建一个专门分析股票市场数据的agent"""
    system_message = (
        f"你是一位专业的股票市场分析师，擅长分析A股市场和{stock_name}数据并提供见解。"
        f"你需要分析上证指数和{stock_name}的表现，包括日线、周线、月线数据，"
        "识别它们的短期趋势，确定关键支撑位和阻力位，"
        "并基于技术分析给出未来可能的走势预测。"
        "请在分析中特别关注：均线系统配置、MACD等技术指标、量价关系、支撑与阻力水平，以及大盘与个股关系。"
        "请提供专业、客观的分析，并给出你的推理过程。"
    )
    # 使用最新版本的camel-ai API初始化ChatAgent
    from camel.models import DeepSeekModel
    from camel.types import ModelType
    model = DeepSeekModel(model_type="deepseek-chat", api_key=DEEPSEEK_API_KEY)
    return ChatAgent(system_message=system_message, model=model)

# 带重试机制的函数装饰器
def with_retry(func):
    """添加重试机制的装饰器"""
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < MAX_RETRIES:
            try:
                return func(*args, **kwargs)
            except (RequestException, HTTPError, ConnectionError, TimeoutError) as e:
                retries += 1
                if retries < MAX_RETRIES:
                    print(f"网络错误: {e}. 第{retries}次重试, {RETRY_DELAY}秒后...")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"重试{MAX_RETRIES}次后失败: {e}")
                    return None
            except Exception as e:
                print(f"发生其他错误: {e}")
                return None
    return wrapper

# 获取股票或指数数据 - 支持不同周期
@with_retry
def get_stock_data(symbol="sh000001", days=30, period="daily"):
    """获取股票或指数的历史数据
    
    参数:
    symbol -- 股票代码，默认为上证指数(sh000001)
    days -- 获取历史数据的天数，默认为30天
    period -- 周期类型，可选值：'daily'（日线）, 'weekly'（周线）, 'monthly'（月线）
    
    返回:
    DataFrame -- 包含股票历史数据的DataFrame
    """
    try:
        # 转换周期参数以适应akshare接口
        ak_period = period
        if period == "weekly":
            ak_period = "week"
        elif period == "monthly":
            ak_period = "month"
            
        if symbol.startswith("sh") or symbol.startswith("sz"):
            # 如果是指数，使用指数数据接口
            if period == "daily":
                df = ak.stock_zh_index_daily(symbol=symbol)
            elif period == "weekly":
                df = ak.stock_zh_index_weekly(symbol=symbol)
            elif period == "monthly":
                df = ak.stock_zh_index_monthly(symbol=symbol)
            else:
                raise ValueError(f"不支持的周期类型: {period}，支持的类型为: daily, weekly, monthly")
        else:
            # 否则使用A股数据接口
            # 在akshare中，A股代码不需要前缀，直接使用数字代码
            start_date = (datetime.now() - timedelta(days=days*2)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")
            print(f"获取{period}股票数据: {symbol}, 从 {start_date} 到 {end_date}")
            
            df = ak.stock_zh_a_hist(symbol=symbol, period=ak_period, 
                                    start_date=start_date,
                                    end_date=end_date)
            # 重命名列名，确保与指数数据接口返回格式一致
            df.rename(columns={"开盘": "open", "收盘": "close", "最高": "high", 
                              "最低": "low", "成交量": "volume", "日期": "date"}, inplace=True)
            # 将日期列设为索引
            if "date" in df.columns:
                df.set_index("date", inplace=True)
        
        # 确保数据按日期排序
        df = df.sort_index(ascending=False)
        # 获取最近指定天数的数据
        df = df.head(days)
        
        if df.empty:
            print(f"警告: 获取到的{period}数据为空，请检查股票代码 {symbol} 是否正确")
            return None
            
        return df
    except Exception as e:
        print(f"获取{period}股票数据时出错: {e}")
        raise  # 重新抛出异常，让装饰器捕获并重试

# 获取股票名称
@with_retry
def get_stock_name(symbol):
    """根据股票代码获取股票名称"""
    try:
        if symbol == "sh000001":
            return "上证指数"
        elif symbol.startswith("sh") or symbol.startswith("sz"):
            # 对于指数，可以使用指数列表查询
            print("正在查询指数名称...")
            indices = ak.stock_zh_index_spot()
            symbol_upper = symbol.upper()
            matched = indices[indices['代码'] == symbol_upper]
            if not matched.empty:
                return matched.iloc[0]['名称']
            return f"指数{symbol}"
        else:
            # 对于A股，使用股票列表查询
            print("正在查询股票名称...")
            try:
                # 首先尝试使用股票代码查询
                stock_info = ak.stock_individual_info_em(symbol=symbol)
                if stock_info is not None and not stock_info.empty:
                    # 提取股票名称
                    for index, row in stock_info.iterrows():
                        if row['item'] == '股票简称':
                            return row['value']
            except Exception as e:
                print(f"通过个股信息查询股票名称失败: {e}，尝试其他方式...")
            
            # 如果上面的方法失败，尝试从股票列表中查询
            stocks = ak.stock_info_a_code_name()
            matched = stocks[stocks['code'] == symbol]
            if not matched.empty:
                return matched.iloc[0]['name']
            
            # 所有方法都失败，返回默认名称
            return f"股票{symbol}"
    except Exception as e:
        print(f"获取股票名称时出错: {e}")
        raise  # 重新抛出异常，让装饰器捕获并重试

# 生成数据分析报告
def generate_analysis_report(data, stock_name="上证指数"):
    """生成股票分析报告"""
    if data is None or data.empty:
        return f"无法获取{stock_name}数据，请检查网络连接或API状态。"
    
    # 获取最新一天的数据
    latest_day = data.iloc[0]
    previous_day = data.iloc[1]
    
    # 计算当天涨跌幅
    change_pct = (latest_day['close'] - previous_day['close']) / previous_day['close'] * 100
    
    # 准备分析师需要的数据
    # 将numpy.int64类型的日期转换为字符串格式
    date_str = str(latest_day.name) if isinstance(latest_day.name, (int, np.int64)) else latest_day.name.strftime("%Y-%m-%d")
    analysis_data = {
        "股票名称": stock_name,
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

# 获取英文安全的股票名称
def get_safe_stock_name(symbol, stock_name=None):
    """获取用于显示的安全股票名称，避免中文字体问题"""
    if stock_name is None:
        return f"Stock {symbol}"
    
    # 如果是中文名称和已知的特殊索引，返回英文替代
    if stock_name == "上证指数":
        return "SSE Index (sh000001)"
    elif stock_name == "深证成指":
        return "SZSE Index (sz399001)"
    elif stock_name == "创业板指":
        return "ChiNext Index (sz399006)"
    else:
        # 对于其他股票，使用代码作为名称
        safe_name = f"{stock_name} ({symbol})"
        return safe_name

# 可视化股票数据
def visualize_stock_data(data, stock_name="上证指数", symbol="sh000001"):
    """生成股票走势图"""
    if data is None or data.empty:
        return None
    
    # 获取安全的英文股票名称
    safe_name = get_safe_stock_name(symbol, stock_name)
    clean_filename = safe_name.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
    
    # 使用英文标签
    chart_title = f'{safe_name} Price Chart'
    x_label = 'Date'
    y_label = 'Price'
    legend_labels = ['Close', '5-Day MA', '10-Day MA', '20-Day MA']
    
    # 反转数据以便按时间顺序显示
    plot_data = data.iloc[::-1]
    
    # 创建图表
    plt.figure(figsize=(12, 6))
    
    # 绘制线条
    plt.plot(plot_data.index, plot_data['close'], label=legend_labels[0], color='#1f77b4')
    plt.plot(plot_data.index, plot_data['close'].rolling(window=5).mean(), label=legend_labels[1], color='#ff7f0e')
    plt.plot(plot_data.index, plot_data['close'].rolling(window=10).mean(), label=legend_labels[2], color='#2ca02c')
    plt.plot(plot_data.index, plot_data['close'].rolling(window=20).mean(), label=legend_labels[3], color='#d62728')
    
    # 设置图表标题和标签
    plt.title(chart_title, fontsize=14)
    plt.xlabel(x_label, fontsize=12)
    plt.ylabel(y_label, fontsize=12)
    
    # 完善图表样式
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 添加水印
    fig = plt.gcf()
    fig.text(0.95, 0.05, f'Stock Analysis - {clean_filename}', fontsize=8, color='gray', 
             ha='right', va='bottom', alpha=0.5)
    
    # 保存图表
    chart_path = f'{clean_filename}_trend.png'
    plt.savefig(chart_path, dpi=120)
    plt.close()
    
    print(f"图表已保存: {chart_path}")
    return chart_path

# 生成Markdown格式的分析报告
def generate_markdown_report(analysis_data, analysis_content, chart_path):
    """生成Markdown格式的分析报告并保存为文件"""
    stock_name = analysis_data['股票名称']
    
    # 创建Markdown格式的报告
    markdown_report = f"""# {stock_name}分析报告

## 基本信息

- **股票名称**: {stock_name}
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

![{stock_name}走势图]({chart_path})

---
*本报告由AI分析师生成，仅供参考，不构成投资建议*
"""
    
    # 保存为Markdown文件
    safe_name = stock_name.replace(" ", "_").replace("/", "_")
    report_filename = f"{safe_name}_分析报告_{analysis_data['日期']}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    
    return report_filename

# 计算趋势指标
def calculate_trend_indicators(data):
    """计算趋势相关指标"""
    if data is None or data.empty:
        return None
    
    # 复制数据，避免修改原始数据
    df = data.copy()
    
    # 计算常用技术指标
    # 1. 移动平均线
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    
    # 2. MACD
    df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Histogram'] = df['MACD'] - df['Signal']
    
    # 3. RSI (相对强弱指标)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 4. 布林带
    df['Middle_Band'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    df['Upper_Band'] = df['Middle_Band'] + (std * 2)
    df['Lower_Band'] = df['Middle_Band'] - (std * 2)
    
    return df

# 分析短期趋势
def analyze_short_term_trend(data):
    """分析股票短期趋势，返回趋势分析结果"""
    if data is None or data.empty:
        return "无法获取足够的数据进行短期趋势分析"
    
    # 使用计算好的技术指标
    df = data.copy()
    
    # 初始化趋势分析结果
    trend_analysis = {
        "trend": "Unknown",  # 上升、下降、盘整
        "strength": 0,       # 0-100的强度
        "signals": [],       # 信号列表
        "description": ""    # 详细描述
    }
    
    # 1. 基于均线判断趋势
    latest = df.iloc[0]
    prev = df.iloc[1] if len(df) > 1 else None
    
    # 均线多头排列判断（MA5 > MA10 > MA20）
    if 'MA5' in df.columns and 'MA10' in df.columns and 'MA20' in df.columns:
        ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
        ma_bearish = latest['MA5'] < latest['MA10'] < latest['MA20']
        
        if ma_bullish:
            trend_analysis["trend"] = "上升"
            trend_analysis["signals"].append("均线多头排列")
            trend_analysis["strength"] += 30
        elif ma_bearish:
            trend_analysis["trend"] = "下降"
            trend_analysis["signals"].append("均线空头排列")
            trend_analysis["strength"] += 30
    
    # 2. 价格与均线关系判断
    if 'MA5' in df.columns and 'MA10' in df.columns:
        price_above_ma5 = latest['close'] > latest['MA5']
        price_above_ma10 = latest['close'] > latest['MA10']
        
        if price_above_ma5 and price_above_ma10:
            if trend_analysis["trend"] != "上升":
                trend_analysis["trend"] = "上升"
            trend_analysis["signals"].append("价格站上短期均线")
            trend_analysis["strength"] += 15
        elif not price_above_ma5 and not price_above_ma10:
            if trend_analysis["trend"] != "下降":
                trend_analysis["trend"] = "下降"
            trend_analysis["signals"].append("价格跌破短期均线")
            trend_analysis["strength"] += 15
    
    # 3. MACD判断
    if 'MACD' in df.columns and 'Signal' in df.columns:
        # MACD金叉判断
        if prev is not None and prev['MACD'] < prev['Signal'] and latest['MACD'] > latest['Signal']:
            trend_analysis["trend"] = "上升"
            trend_analysis["signals"].append("MACD金叉")
            trend_analysis["strength"] += 25
        # MACD死叉判断
        elif prev is not None and prev['MACD'] > prev['Signal'] and latest['MACD'] < latest['Signal']:
            trend_analysis["trend"] = "下降"
            trend_analysis["signals"].append("MACD死叉")
            trend_analysis["strength"] += 25
        # MACD柱状图方向
        elif 'Histogram' in df.columns and len(df) > 2:
            hist_increasing = df['Histogram'].iloc[0] > df['Histogram'].iloc[1] > df['Histogram'].iloc[2]
            hist_decreasing = df['Histogram'].iloc[0] < df['Histogram'].iloc[1] < df['Histogram'].iloc[2]
            
            if hist_increasing:
                if trend_analysis["trend"] != "上升":
                    trend_analysis["trend"] = "上升趋势增强"
                trend_analysis["signals"].append("MACD柱状图连续增加")
                trend_analysis["strength"] += 10
            elif hist_decreasing:
                if trend_analysis["trend"] != "下降":
                    trend_analysis["trend"] = "下降趋势增强"
                trend_analysis["signals"].append("MACD柱状图连续减少")
                trend_analysis["strength"] += 10
    
    # 4. RSI判断
    if 'RSI' in df.columns:
        rsi = latest['RSI']
        
        if rsi > 70:
            trend_analysis["signals"].append(f"RSI超买({rsi:.2f})")
            if trend_analysis["trend"] == "上升":
                trend_analysis["trend"] = "上升但接近阻力位"
        elif rsi < 30:
            trend_analysis["signals"].append(f"RSI超卖({rsi:.2f})")
            if trend_analysis["trend"] == "下降":
                trend_analysis["trend"] = "下降但接近支撑位"
    
    # 5. 成交量判断
    if 'volume' in df.columns and len(df) > 5:
        avg_volume = df['volume'].iloc[1:6].mean()  # 计算前5天的平均成交量
        latest_volume = df['volume'].iloc[0]
        
        volume_change = (latest_volume - avg_volume) / avg_volume * 100
        
        if volume_change > 30:  # 成交量显著放大
            if trend_analysis["trend"] == "上升":
                trend_analysis["signals"].append("成交量放大，上升趋势确认")
                trend_analysis["strength"] += 20
            elif trend_analysis["trend"] == "下降":
                trend_analysis["signals"].append("成交量放大，下降趋势确认")
                trend_analysis["strength"] += 20
            else:
                trend_analysis["signals"].append("成交量放大，趋势转变信号")
    
    # 根据信号数量和强度确定描述
    if trend_analysis["strength"] >= 70:
        strength_desc = "强烈"
    elif trend_analysis["strength"] >= 40:
        strength_desc = "中等"
    else:
        strength_desc = "弱"
    
    # 如果还是Unknown但有信号，根据信号判断
    if trend_analysis["trend"] == "Unknown" and trend_analysis["signals"]:
        bullish_signals = sum(1 for s in trend_analysis["signals"] if "上升" in s or "多头" in s or "金叉" in s)
        bearish_signals = sum(1 for s in trend_analysis["signals"] if "下降" in s or "空头" in s or "死叉" in s)
        
        if bullish_signals > bearish_signals:
            trend_analysis["trend"] = "可能上升"
        elif bearish_signals > bullish_signals:
            trend_analysis["trend"] = "可能下降"
        else:
            trend_analysis["trend"] = "盘整"
    elif not trend_analysis["signals"]:
        trend_analysis["trend"] = "盘整"
    
    # 生成描述
    trend_analysis["description"] = f"{strength_desc}{trend_analysis['trend']}趋势，信号包括：{'、'.join(trend_analysis['signals'])}"
    
    return trend_analysis

# 寻找支撑位和阻力位
def find_support_resistance(data, n_levels=3):
    """
    发现股票数据中的支撑位和阻力位
    
    参数:
    data -- 股票数据DataFrame
    n_levels -- 返回的支撑位和阻力位数量（各自）
    
    返回:
    dict -- 包含支撑位和阻力位的字典
    """
    if data is None or data.empty or len(data) < 20:
        return {"support": [], "resistance": [], "description": "数据不足，无法分析支撑位和阻力位"}
    
    # 复制并准备数据
    df = data.copy()
    
    # 获取价格范围
    latest_price = df['close'].iloc[0]
    price_min = df['low'].min()
    price_max = df['high'].max()
    
    # 方法1: 基于历史高低点寻找支撑位和阻力位
    # 找出局部高点和低点
    local_highs = []
    local_lows = []
    
    for i in range(2, len(df) - 2):
        # 局部高点: 当前高点比前后两个交易日的高点都要高
        if df['high'].iloc[i] > df['high'].iloc[i-1] and df['high'].iloc[i] > df['high'].iloc[i-2] and \
           df['high'].iloc[i] > df['high'].iloc[i+1] and df['high'].iloc[i] > df['high'].iloc[i+2]:
            local_highs.append(df['high'].iloc[i])
        
        # 局部低点: 当前低点比前后两个交易日的低点都要低
        if df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i-2] and \
           df['low'].iloc[i] < df['low'].iloc[i+1] and df['low'].iloc[i] < df['low'].iloc[i+2]:
            local_lows.append(df['low'].iloc[i])
    
    # 方法2: 布林带作为动态支撑位和阻力位
    if 'Upper_Band' in df.columns and 'Lower_Band' in df.columns:
        latest_upper = df['Upper_Band'].iloc[0]
        latest_lower = df['Lower_Band'].iloc[0]
        
        local_highs.append(latest_upper)
        local_lows.append(latest_lower)
    
    # 方法3: 近期的高低点
    for i in range(5):
        if i < len(df):
            local_highs.append(df['high'].iloc[i])
            local_lows.append(df['low'].iloc[i])
    
    # 方法4: 心理价位(整数关口)
    # 获取最近的整数关口
    price_digits = len(str(int(latest_price)))
    magnitude = 10 ** (price_digits - 2)  # 对于3000点附近，取100为单位
    
    for i in range(-10, 11):
        level = round((latest_price + i * magnitude) / magnitude) * magnitude
        if price_min < level < price_max:  # 只添加在价格范围内的心理关口
            if level > latest_price:
                local_highs.append(level)
            elif level < latest_price:
                local_lows.append(level)
    
    # 合并价格点，排序，并去除重复值和太接近的值
    def merge_close_levels(levels, threshold_pct=0.02):
        if not levels:
            return []
        
        # 排序
        sorted_levels = sorted(levels)
        merged_levels = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            # 检查是否与最近添加的价位太接近
            if (level - merged_levels[-1]) / merged_levels[-1] > threshold_pct:
                merged_levels.append(level)
                
        return merged_levels
    
    # 合并接近的价格水平
    support_levels = merge_close_levels([l for l in local_lows if l < latest_price])
    resistance_levels = merge_close_levels([l for l in local_highs if l > latest_price])
    
    # 选择最接近当前价格的几个水平
    support_levels = sorted(support_levels, reverse=True)[:n_levels] if support_levels else []
    resistance_levels = sorted(resistance_levels)[:n_levels] if resistance_levels else []
    
    # 计算与当前价格的距离百分比
    supports_with_dist = [(level, (latest_price - level) / level * 100) for level in support_levels]
    resistances_with_dist = [(level, (level - latest_price) / latest_price * 100) for level in resistance_levels]
    
    # 生成文字描述
    support_desc = []
    for level, dist in supports_with_dist:
        strength = "强" if dist < 3 else "中" if dist < 7 else "弱"
        support_desc.append(f"{level:.2f}({strength}支撑，距今{dist:.2f}%)")
    
    resistance_desc = []
    for level, dist in resistances_with_dist:
        strength = "强" if dist < 3 else "中" if dist < 7 else "弱"
        resistance_desc.append(f"{level:.2f}({strength}阻力，距今{dist:.2f}%)")
    
    result = {
        "support": support_levels,
        "resistance": resistance_levels,
        "support_dist": supports_with_dist,
        "resistance_dist": resistances_with_dist,
        "description": f"主要支撑位：{'、'.join(support_desc) if support_desc else '无明显支撑位'}\n"
                      f"主要阻力位：{'、'.join(resistance_desc) if resistance_desc else '无明显阻力位'}"
    }
    
    return result

# 可视化包含支撑位和阻力位的股票数据
def visualize_stock_with_sr(data, stock_name, sr_levels, period="daily", symbol=None):
    """生成包含支撑位和阻力位的股票走势图"""
    if data is None or data.empty:
        return None
        
    # 获取英文时间段名称
    period_english = {
        "日线": "Daily", 
        "周线": "Weekly", 
        "月线": "Monthly",
        "daily": "Daily",
        "weekly": "Weekly",
        "monthly": "Monthly"
    }.get(period, period)
    
    # 获取安全的英文股票名称
    if symbol is None:
        if stock_name == "上证指数":
            symbol = "sh000001"
        elif "贵州茅台" in stock_name:
            symbol = "600519"
        else:
            # 尝试从股票名称中提取可能的股票代码
            import re
            symbol_match = re.search(r'(\d{6})', stock_name)
            symbol = symbol_match.group(1) if symbol_match else "Unknown"
    
    safe_name = get_safe_stock_name(symbol, stock_name)
    clean_filename = safe_name.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
    
    # 使用英文标签
    chart_title = f'{safe_name} {period_english} Chart'
    x_label = 'Date'
    y_label = 'Price'
    legend_labels = ['Close', '5-Day MA', '10-Day MA', '20-Day MA']
    
    # 反转数据以便按时间顺序显示
    plot_data = data.iloc[::-1]
    
    # 创建图表
    plt.figure(figsize=(14, 8))
    
    # 绘制价格线条
    plt.plot(plot_data.index, plot_data['close'], label=legend_labels[0], color='#1f77b4', linewidth=2)
    
    # 绘制均线
    if 'MA5' in plot_data.columns:
        plt.plot(plot_data.index, plot_data['MA5'], label=legend_labels[1], color='#ff7f0e', linewidth=1.5)
    else:
        plt.plot(plot_data.index, plot_data['close'].rolling(window=5).mean(), label=legend_labels[1], color='#ff7f0e', linewidth=1.5)
        
    if 'MA10' in plot_data.columns:
        plt.plot(plot_data.index, plot_data['MA10'], label=legend_labels[2], color='#2ca02c', linewidth=1.5)
    else:
        plt.plot(plot_data.index, plot_data['close'].rolling(window=10).mean(), label=legend_labels[2], color='#2ca02c', linewidth=1.5)
        
    if 'MA20' in plot_data.columns:
        plt.plot(plot_data.index, plot_data['MA20'], label=legend_labels[3], color='#d62728', linewidth=1.5)
    else:
        plt.plot(plot_data.index, plot_data['close'].rolling(window=20).mean(), label=legend_labels[3], color='#d62728', linewidth=1.5)
    
    # 绘制支撑位和阻力位
    latest_price = plot_data['close'].iloc[-1]
    y_min, y_max = plt.ylim()
    
    # 添加水平线表示支撑位
    for i, support in enumerate(sr_levels.get('support', [])):
        plt.axhline(y=support, color='g', linestyle='--', alpha=0.7, 
                   label=f"Support {i+1}: {support:.2f}")
        
        # 添加支撑位标签
        plt.text(plot_data.index[-1], support, f"{support:.2f}", 
                color='g', fontsize=9, ha='left', va='center')
    
    # 添加水平线表示阻力位
    for i, resistance in enumerate(sr_levels.get('resistance', [])):
        plt.axhline(y=resistance, color='r', linestyle='--', alpha=0.7, 
                    label=f"Resist {i+1}: {resistance:.2f}")
        
        # 添加阻力位标签
        plt.text(plot_data.index[-1], resistance, f"{resistance:.2f}", 
                color='r', fontsize=9, ha='left', va='center')
    
    # 设置图表标题和标签
    plt.title(chart_title, fontsize=16)
    plt.xlabel(x_label, fontsize=12)
    plt.ylabel(y_label, fontsize=12)
    
    # 完善图表样式
    plt.legend(loc='upper left')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 添加水印
    fig = plt.gcf()
    fig.text(0.95, 0.05, f'Stock Analysis - {clean_filename} {period_english}', fontsize=8, color='gray', 
             ha='right', va='bottom', alpha=0.5)
    
    # 保存图表
    chart_path = f'{clean_filename}_{period_english}_trend_sr.png'
    plt.savefig(chart_path, dpi=150)
    plt.close()
    
    print(f"{period_english}图表已保存: {chart_path}")
    return chart_path

# 修复akshare周线和月线数据获取
@with_retry
def get_stock_period_data(symbol, days=30, period="daily"):
    """获取股票不同周期数据的兼容实现，使用日线数据转换"""
    try:
        if period == "daily":
            # 直接获取日线数据
            return get_stock_data(symbol, days, period)
        
        # 对于周线和月线，我们获取更长时间的日线数据，然后手动转换
        # 为确保有足够数据，获取足够长的历史
        extra_days = days * 7 if period == "weekly" else days * 30
        daily_data = get_stock_data(symbol, extra_days, "daily")
        
        if daily_data is None or daily_data.empty:
            return None
            
        # 确保有索引列
        if daily_data.index.name == 'date' or isinstance(daily_data.index, pd.DatetimeIndex):
            # 如果日期已经是索引，先重置
            daily_data = daily_data.reset_index()
        
        # 确保日期列存在
        if 'date' not in daily_data.columns:
            print(f"警告: 日期列不存在于数据中，列名为: {daily_data.columns.tolist()}")
            # 尝试查找可能的日期列
            possible_date_columns = [col for col in daily_data.columns if '日期' in col or 'date' in col.lower()]
            if possible_date_columns:
                print(f"使用替代日期列: {possible_date_columns[0]}")
                daily_data['date'] = daily_data[possible_date_columns[0]]
            else:
                # 如果找不到日期列，创建一个基于索引的日期列
                print("未找到日期列，创建基于索引的日期列")
                daily_data['date'] = pd.date_range(end=datetime.now(), periods=len(daily_data))
        
        # 确保日期列是datetime类型
        if isinstance(daily_data['date'].iloc[0], str):
            try:
                # 尝试转换日期字符串为datetime
                daily_data['date'] = pd.to_datetime(daily_data['date'], errors='coerce')
            except Exception as e:
                print(f"转换日期列为datetime时出错: {e}")
                # 创建一个数值序列作为年月标识
                print("使用数值序列代替日期")
                if period == "weekly":
                    # 使用连续的周序列
                    daily_data['year_week'] = [f"Week-{i}" for i in range(1, len(daily_data) + 1)]
                else:
                    # 使用连续的月序列
                    daily_data['year_month'] = [f"Month-{i}" for i in range(1, len(daily_data) + 1)]
                
                # 按序列分组
                if period == "weekly":
                    # 每7行作为一周
                    groups = [daily_data.iloc[i:i+7] for i in range(0, len(daily_data), 7)]
                else:
                    # 每30行作为一月
                    groups = [daily_data.iloc[i:i+30] for i in range(0, len(daily_data), 30)]
                
                # 手动聚合
                result_data = pd.DataFrame()
                for i, group in enumerate(groups):
                    if not group.empty:
                        row = {
                            'date': group['date'].iloc[0],
                            'open': group['open'].iloc[0],
                            'high': group['high'].max(),
                            'low': group['low'].min(),
                            'close': group['close'].iloc[-1],
                            'volume': group['volume'].sum()
                        }
                        result_data = pd.concat([result_data, pd.DataFrame([row])], ignore_index=True)
                
                # 设置日期为索引并确保正确排序
                if len(result_data) > 0:
                    result_data = result_data.sort_index(ascending=False)
                    return result_data.head(days)
                else:
                    return None
        
        # 根据日期进行周/月的转换
        if period == "weekly":
            try:
                # 添加周数据列，将日期转为周
                # 创建年和周标识
                daily_data['year_week'] = daily_data['date'].dt.strftime('%Y-%U')
                
                # 按周分组，取每周的开盘、最高、最低、收盘、成交量
                weekly_data = daily_data.groupby('year_week').agg(
                    date=('date', 'first'),
                    open=('open', 'first'),
                    high=('high', 'max'),
                    low=('low', 'min'),
                    close=('close', 'last'),
                    volume=('volume', 'sum')
                )
                
                # 恢复日期作为索引，并返回最近的days行
                weekly_data.set_index('date', inplace=True)
                weekly_data.sort_index(ascending=False, inplace=True)
                return weekly_data.head(days)
            except Exception as e:
                print(f"处理周数据时出错: {e}")
                # 如果使用datetime转换失败，尝试替代方法
                # 每7行作为一周
                groups = [daily_data.iloc[i:i+7] for i in range(0, len(daily_data), 7)]
                result_data = pd.DataFrame()
                for i, group in enumerate(groups):
                    if not group.empty:
                        row = {
                            'date': group['date'].iloc[0],
                            'open': group['open'].iloc[0],
                            'high': group['high'].max(),
                            'low': group['low'].min(),
                            'close': group['close'].iloc[-1],
                            'volume': group['volume'].sum()
                        }
                        result_data = pd.concat([result_data, pd.DataFrame([row])], ignore_index=True)
                
                # 设置日期为索引并确保正确排序
                if len(result_data) > 0:
                    result_data.set_index('date', inplace=True)
                    result_data = result_data.sort_index(ascending=False)
                    return result_data.head(days)
                
        elif period == "monthly":
            try:
                # 添加月数据列，将日期转为月
                # 创建年月标识
                daily_data['year_month'] = daily_data['date'].dt.strftime('%Y-%m')
                
                # 按月分组，取每月的开盘、最高、最低、收盘、成交量
                monthly_data = daily_data.groupby('year_month').agg(
                    date=('date', 'first'),
                    open=('open', 'first'),
                    high=('high', 'max'),
                    low=('low', 'min'),
                    close=('close', 'last'),
                    volume=('volume', 'sum')
                )
                
                # 恢复日期作为索引，并返回最近的days行
                monthly_data.set_index('date', inplace=True)
                monthly_data.sort_index(ascending=False, inplace=True)
                return monthly_data.head(days)
            except Exception as e:
                print(f"处理月数据时出错: {e}")
                # 如果使用datetime转换失败，尝试替代方法
                # 每30行作为一月
                groups = [daily_data.iloc[i:i+30] for i in range(0, len(daily_data), 30)]
                result_data = pd.DataFrame()
                for i, group in enumerate(groups):
                    if not group.empty:
                        row = {
                            'date': group['date'].iloc[0],
                            'open': group['open'].iloc[0],
                            'high': group['high'].max(),
                            'low': group['low'].min(),
                            'close': group['close'].iloc[-1],
                            'volume': group['volume'].sum()
                        }
                        result_data = pd.concat([result_data, pd.DataFrame([row])], ignore_index=True)
                
                # 设置日期为索引并确保正确排序
                if len(result_data) > 0:
                    result_data.set_index('date', inplace=True)
                    result_data = result_data.sort_index(ascending=False)
                    return result_data.head(days)
        
        print(f"无法将日线数据转换为{period}数据")
        return None
    except Exception as e:
        print(f"获取{period}周期股票数据时出错: {e}")
        raise

# 主函数
def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='股票分析工具')
    parser.add_argument('--symbol', type=str, default="600519", 
                        help='股票代码，例如：600000（上海）或000001（深圳）；默认为贵州茅台')
    parser.add_argument('--days', type=int, default=30, 
                        help='分析的历史数据天数，默认为30天')
    args = parser.parse_args()
    
    # 存储所有数据和分析结果
    analysis_results = {}
    
    # 1. 无论用户指定什么，都先下载上证指数的日周月数据
    print("===== 正在获取上证指数数据 =====")
    index_symbol = "sh000001"
    index_name = "上证指数"
    
    # 获取上证指数的多周期数据
    index_data = {}
    index_analysis = {}
    index_charts = {}
    
    # 确保至少有一个周期的数据可用
    has_index_data = False
    
    for period in ["daily", "weekly", "monthly"]:
        period_chinese = {"daily": "日线", "weekly": "周线", "monthly": "月线"}[period]
        print(f"正在获取上证指数{period_chinese}数据...")
        
        try:
            # 尝试使用旧方法
            if period == "daily":
                index_data[period] = get_stock_data(index_symbol, args.days, period)
            else:
                # 对于周线和月线，使用我们的兼容实现
                index_data[period] = get_stock_period_data(index_symbol, args.days, period)
                
            if index_data[period] is not None:
                # 计算技术指标
                index_data[period] = calculate_trend_indicators(index_data[period])
                print(f"上证指数{period_chinese}数据获取成功。")
                
                # 设置标志，表示至少有一个周期的数据可用
                has_index_data = True
                
                # 分析上证指数的趋势和支撑/阻力位
                print(f"分析上证指数{period_chinese}趋势...")
                
                # 分析趋势
                trend_analysis = analyze_short_term_trend(index_data[period])
                
                # 寻找支撑位和阻力位
                sr_levels = find_support_resistance(index_data[period])
                
                # 保存分析结果
                index_analysis[period] = {
                    "trend": trend_analysis,
                    "support_resistance": sr_levels
                }
                
                # 生成图表 - 传递正确的股票代码
                chart_path = visualize_stock_with_sr(index_data[period], index_name, sr_levels, period, index_symbol)
                index_charts[period] = chart_path
            else:
                print(f"警告: 上证指数{period_chinese}数据获取失败")
                # 初始化空的分析结果，避免后续KeyError
                index_analysis[period] = {
                    "trend": {"description": f"无法获取上证指数{period_chinese}数据"},
                    "support_resistance": {"description": f"无法分析上证指数{period_chinese}支撑位和阻力位"}
                }
        except Exception as e:
            print(f"处理上证指数{period_chinese}数据时出错: {e}")
            # 初始化空的分析结果，避免后续KeyError
            index_analysis[period] = {
                "trend": {"description": f"处理上证指数{period_chinese}数据时出错"},
                "support_resistance": {"description": f"无法分析上证指数{period_chinese}支撑位和阻力位"}
            }
            
    # 2. 获取用户指定的股票数据
    user_stock_symbol = args.symbol
    print(f"\n===== 正在获取股票代码 {user_stock_symbol} 的数据 =====")
    
    # 获取股票名称
    stock_name = get_stock_name(user_stock_symbol)
    print(f"股票名称识别为: {stock_name}")
    
    # 获取股票的多周期数据
    stock_data = {}
    stock_analysis = {}
    stock_charts = {}
    
    # 确保至少有一个周期的数据可用
    has_stock_data = False
    
    for period in ["daily", "weekly", "monthly"]:
        period_chinese = {"daily": "日线", "weekly": "周线", "monthly": "月线"}[period]
        print(f"正在获取{stock_name}{period_chinese}数据...")
        
        try:
            # 尝试使用旧方法
            if period == "daily":
                stock_data[period] = get_stock_data(user_stock_symbol, args.days, period)
            else:
                # 对于周线和月线，使用我们的兼容实现
                stock_data[period] = get_stock_period_data(user_stock_symbol, args.days, period)
            
            if stock_data[period] is not None:
                # 计算技术指标
                stock_data[period] = calculate_trend_indicators(stock_data[period])
                print(f"{stock_name}{period_chinese}数据获取成功。")
                
                # 设置标志，表示至少有一个周期的数据可用
                has_stock_data = True
                
                # 分析股票的趋势和支撑/阻力位
                print(f"分析{stock_name}{period_chinese}趋势...")
                
                # 分析趋势
                trend_analysis = analyze_short_term_trend(stock_data[period])
                
                # 寻找支撑位和阻力位
                sr_levels = find_support_resistance(stock_data[period])
                
                # 保存分析结果
                stock_analysis[period] = {
                    "trend": trend_analysis,
                    "support_resistance": sr_levels
                }
                
                # 生成图表 - 传递正确的股票代码
                chart_path = visualize_stock_with_sr(stock_data[period], stock_name, sr_levels, period, user_stock_symbol)
                stock_charts[period] = chart_path
            else:
                print(f"警告: {stock_name}{period_chinese}数据获取失败")
                # 初始化空的分析结果，避免后续KeyError
                stock_analysis[period] = {
                    "trend": {"description": f"无法获取{stock_name}{period_chinese}数据"},
                    "support_resistance": {"description": f"无法分析{stock_name}{period_chinese}支撑位和阻力位"}
                }
        except Exception as e:
            print(f"处理{stock_name}{period_chinese}数据时出错: {e}")
            # 初始化空的分析结果，避免后续KeyError
            stock_analysis[period] = {
                "trend": {"description": f"处理{stock_name}{period_chinese}数据时出错"},
                "support_resistance": {"description": f"无法分析{stock_name}{period_chinese}支撑位和阻力位"}
            }
    
    # 5. 生成日线数据基础报告（兼容原有逻辑）
    if has_stock_data and "daily" in stock_data and stock_data["daily"] is not None:
        # 提取原始分析数据
        analysis_data = generate_analysis_report(stock_data["daily"], stock_name)
        
        # 创建分析师agent
        print("\n===== 创建AI分析师生成详细分析报告 =====")
        analyst = create_analyst_agent(stock_name)
        
        # 准备提问，只包含有效的数据
        prompt = f"""
        请分析以下市场数据，并给出市场状况、趋势预测和建议：
        
        ## 上证指数分析
        - 日线趋势: {index_analysis['daily']['trend']['description']}
        - 日线支撑阻力: {index_analysis['daily']['support_resistance']['description']}
        """
        
        # 添加周线和月线分析，如果有的话
        if "weekly" in index_analysis:
            prompt += f"- 周线趋势: {index_analysis['weekly']['trend']['description']}\n"
        if "monthly" in index_analysis:
            prompt += f"- 月线趋势: {index_analysis['monthly']['trend']['description']}\n"
        
        prompt += f"""
        ## {stock_name}分析
        - 股票名称: {stock_name}
        - 日期: {analysis_data['日期']}
        - 当前价格: {analysis_data['收盘价']}
        - 涨跌幅: {analysis_data['涨跌幅']}
        
        - 日线趋势: {stock_analysis['daily']['trend']['description']}
        - 日线支撑阻力: {stock_analysis['daily']['support_resistance']['description']}
        """
        
        # 添加周线和月线分析，如果有的话
        if "weekly" in stock_analysis:
            prompt += f"- 周线趋势: {stock_analysis['weekly']['trend']['description']}\n"
        if "monthly" in stock_analysis:
            prompt += f"- 月线趋势: {stock_analysis['monthly']['trend']['description']}\n"
        
        prompt += f"""
        - 5日均线: {analysis_data['5日均线']}
        - 10日均线: {analysis_data['10日均线']}
        - 20日均线: {analysis_data['20日均线']}
        
        请提供详细分析，包括：
        1. 大盘分析：上证指数走势分析和对市场整体判断
        2. 个股分析：{stock_name}的走势分析
        3. 趋势判断：短期趋势分析
        4. 支撑阻力：关键价格位置和突破意义
        5. 投资建议：基于目前趋势和支撑阻力位的操作建议
        
        请使用Markdown格式输出，使用标题、列表和强调等Markdown语法使内容更加结构化和易于阅读。
        """
        
        # 发送消息给分析师agent
        print("正在生成AI分析内容...")
        user_message = BaseMessage(role_name="User", role_type="user", meta_dict={}, content=prompt)
        try:
            analyst_response = analyst.step(user_message)
            
            # 提取分析内容
            analysis_content = ""
            try:
                # 从响应中提取消息内容
                if hasattr(analyst_response, 'content'):
                    # 直接获取content属性
                    analysis_content = analyst_response.content
                else:
                    # 转换为字符串并解析
                    response_str = str(analyst_response)
                    if 'content=' in response_str:
                        # 提取content部分，处理可能的转义字符
                        content_start = response_str.find('content=') + 9  # 'content=' 长度为8，加上引号
                        content_end = response_str.find("', video_bytes=") if "', video_bytes=" in response_str else response_str.find("', image_list=")
                        if content_end > content_start:
                            # 处理转义字符
                            raw_content = response_str[content_start:content_end]
                            # 替换转义的换行符为实际的换行符
                            analysis_content = raw_content.replace('\\n', '\n')
                        else:
                            analysis_content = "无法解析分析内容，显示原始响应：\n" + response_str
                    else:
                        analysis_content = response_str
            except Exception as e:
                analysis_content = f"无法获取分析结果: {e}\n响应对象类型: {type(analyst_response)}"
            
            # 生成增强版Markdown报告并保存
            print("正在生成最终分析报告...")
            report_file = generate_enhanced_report(analysis_data, index_analysis, stock_analysis, 
                                                 index_charts, stock_charts, analysis_content)
            
            # 在控制台显示报告已生成的消息
            print(f"\n===== 综合分析报告已生成 =====\n")
            print(f"报告已保存至: {report_file}")
            
        except Exception as e:
            print(f"生成分析报告时出错: {e}")
            print("尝试生成简化版报告...")
            
            # 在AI分析失败的情况下，生成简化版报告
            simplified_analysis = f"""
## 简化分析

### 上证指数分析
- 日线趋势: {index_analysis['daily']['trend']['description']}
- 日线支撑阻力: {index_analysis['daily']['support_resistance']['description']}
"""
            # 添加周线和月线分析，如果有的话
            if "weekly" in index_analysis:
                simplified_analysis += f"- 周线趋势: {index_analysis['weekly']['trend']['description']}\n"
            if "monthly" in index_analysis:
                simplified_analysis += f"- 月线趋势: {index_analysis['monthly']['trend']['description']}\n"

            simplified_analysis += f"""
### {stock_name}分析
- 日线趋势: {stock_analysis['daily']['trend']['description']}
- 日线支撑阻力: {stock_analysis['daily']['support_resistance']['description']}
"""
            # 添加周线和月线分析，如果有的话
            if "weekly" in stock_analysis:
                simplified_analysis += f"- 周线趋势: {stock_analysis['weekly']['trend']['description']}\n"
            if "monthly" in stock_analysis:
                simplified_analysis += f"- 月线趋势: {stock_analysis['monthly']['trend']['description']}\n"

            simplified_analysis += f"""
当前价格: {analysis_data['收盘价']}，与前一日相比{analysis_data['涨跌幅']}
- 与5日均线相比: {analysis_data['收盘价'] - analysis_data['5日均线']:.2f}点
- 与10日均线相比: {analysis_data['收盘价'] - analysis_data['10日均线']:.2f}点
- 与20日均线相比: {analysis_data['收盘价'] - analysis_data['20日均线']:.2f}点

*注：此为简化分析，AI分析服务可能暂时不可用。*
"""
            # 生成简化版报告
            report_file = generate_enhanced_report(analysis_data, index_analysis, stock_analysis, 
                                                 index_charts, stock_charts, simplified_analysis)
            
            print(f"\n===== 综合分析报告(简化版)已生成 =====\n")
            print(f"报告已保存至: {report_file}")
    else:
        print(f"获取{stock_name}数据失败，请检查网络连接或API状态，或确认股票代码是否正确。")

# 生成增强版Markdown格式的分析报告
def generate_enhanced_report(analysis_data, index_analysis, stock_analysis, index_charts, stock_charts, analysis_content):
    """生成包含多周期分析、支撑阻力位的增强版Markdown报告"""
    stock_name = analysis_data['股票名称']
    
    # 创建Markdown格式的报告
    markdown_report = f"""# {stock_name}市场分析报告

## 基本信息

- **股票名称**: {stock_name}
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

## 上证指数分析

### 日线分析
- **趋势**: {index_analysis['daily']['trend']['description']}
- **支撑阻力**: {index_analysis['daily']['support_resistance']['description']}
"""

    # 添加日线图表，如果有的话
    if 'daily' in index_charts and index_charts['daily']:
        markdown_report += f"\n![上证指数日线图]({index_charts['daily']})\n"

    # 添加周线分析，如果有的话
    if 'weekly' in index_analysis:
        markdown_report += f"""
### 周线分析
- **趋势**: {index_analysis['weekly']['trend']['description']}
- **支撑阻力**: {index_analysis['weekly']['support_resistance']['description']}
"""
        if 'weekly' in index_charts and index_charts['weekly']:
            markdown_report += f"\n![上证指数周线图]({index_charts['weekly']})\n"

    # 添加月线分析，如果有的话
    if 'monthly' in index_analysis:
        markdown_report += f"""
### 月线分析
- **趋势**: {index_analysis['monthly']['trend']['description']}
- **支撑阻力**: {index_analysis['monthly']['support_resistance']['description']}
"""
        if 'monthly' in index_charts and index_charts['monthly']:
            markdown_report += f"\n![上证指数月线图]({index_charts['monthly']})\n"

    # 添加股票分析
    markdown_report += f"""
## {stock_name}分析

### 日线分析
- **趋势**: {stock_analysis['daily']['trend']['description']}
- **支撑阻力**: {stock_analysis['daily']['support_resistance']['description']}
"""

    # 添加日线图表，如果有的话
    if 'daily' in stock_charts and stock_charts['daily']:
        markdown_report += f"\n![{stock_name}日线图]({stock_charts['daily']})\n"

    # 添加周线分析，如果有的话
    if 'weekly' in stock_analysis:
        markdown_report += f"""
### 周线分析
- **趋势**: {stock_analysis['weekly']['trend']['description']}
- **支撑阻力**: {stock_analysis['weekly']['support_resistance']['description']}
"""
        if 'weekly' in stock_charts and stock_charts['weekly']:
            markdown_report += f"\n![{stock_name}周线图]({stock_charts['weekly']})\n"

    # 添加月线分析，如果有的话
    if 'monthly' in stock_analysis:
        markdown_report += f"""
### 月线分析
- **趋势**: {stock_analysis['monthly']['trend']['description']}
- **支撑阻力**: {stock_analysis['monthly']['support_resistance']['description']}
"""
        if 'monthly' in stock_charts and stock_charts['monthly']:
            markdown_report += f"\n![{stock_name}月线图]({stock_charts['monthly']})\n"

    # 添加综合分析
    markdown_report += f"""
## 综合市场分析

{analysis_content}

---
*本报告由AI分析师生成，仅供参考，不构成投资建议*
"""
    
    # 保存为Markdown文件
    safe_name = stock_name.replace(" ", "_").replace("/", "_")
    report_filename = f"{safe_name}_市场分析报告_{analysis_data['日期']}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    
    return report_filename

if __name__ == "__main__":
    main()