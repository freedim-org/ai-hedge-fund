#!/usr/bin/env python3
"""
测试EventSource API的脚本
通过命令行发起请求并监听来自服务器的事件推送
"""

import argparse
import json
import sys
import time
import requests
from sseclient import SSEClient
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel

# 全局控制台和任务ID
console = Console()
TASK_ID = None

def get_analysts():
    """获取可用的分析师列表"""
    try:
        response = requests.get("http://192.168.31.168:8000/api/analysts")
        return response.json()["analysts"]
    except Exception as e:
        console.print(f"[bold red]获取分析师列表失败: {str(e)}[/bold red]")
        return []

def get_models():
    """获取可用的模型列表"""
    try:
        response = requests.get("http://192.168.31.168:8000/api/models")
        return [model["model_name"] for model in response.json()["models"]]
    except Exception as e:
        console.print(f"[bold red]获取模型列表失败: {str(e)}[/bold red]")
        return ["gpt-4o"]  # 默认模型

def start_analysis(tickers, analysts, model_name, model_provider="OpenAI"):
    """启动股票分析任务"""
    try:
        data = {
            "tickers": tickers,
            "analysts": analysts,
            "model_name": model_name,
            "model_provider": model_provider,
            "show_reasoning": True
        }
        
        console.print(Panel(f"[bold]启动分析任务[/bold]\n股票: {', '.join(tickers)}\n分析师: {', '.join(analysts)}\n模型: {model_name} ({model_provider})", 
                           title="任务信息", border_style="blue"))
        
        response = requests.post("http://192.168.31.168:8000/api/analysis", json=data)
        if response.status_code != 200:
            console.print(f"[bold red]启动分析失败: {response.text}[/bold red]")
            return None
            
        task_id = response.json()["task_id"]
        console.print(f"[bold green]分析任务已启动，任务ID: {task_id}[/bold green]")
        return task_id
    except Exception as e:
        console.print(f"[bold red]启动分析发生错误: {str(e)} {tickers} {analysts} {model_name} {model_provider}[/bold red]")
        return None

def listen_for_events(task_id):
    """监听事件推送"""
    global TASK_ID
    TASK_ID = task_id
    
    try:
        console.print(f"[bold]开始监听任务 {task_id} 的事件...[/bold]")
        
        # 设置进度条
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            # 创建进度任务
            task = progress.add_task("[cyan]分析进度...", total=100)
            
            # 连接到事件流
            url = f"http://192.168.31.168:8000/api/events/{task_id}"
            
            # 使用 requests 的 Session 对象和 Response.iter_lines 方法手动处理 SSE
            session = requests.Session()
            response = session.get(url, stream=True)
            
            # 确保响应状态码正确
            if response.status_code != 200:
                console.print(f"[bold red]连接事件流失败: {response.text}[/bold red]")
                return
                
            # 手动解析 SSE 事件
            event_type = None
            data_buffer = []
            
            for line in response.iter_lines():
                if not line:
                    # 空行表示事件结束
                    if event_type and data_buffer:
                        # 处理事件
                        event_data = "".join(data_buffer)

                        #console.print(f"[bold blue] {event_type} 事件数据: {event_data}[/bold blue]")
                        
                        # 处理不同类型的事件
                        if event_type == "ping":
                            # 忽略ping事件
                            pass
                        elif event_type == "end":
                            console.print("[bold green]任务完成，事件流已关闭[/bold green]")
                            break
                        elif event_type == "error":
                            console.print(f"[bold red]事件流错误: {event_data}[/bold red]")
                            break
                        elif event_type == "update":
                            try:
                                data = json.loads(event_data)
                                status = data.get("status", "unknown")
                                progress_value = data.get("progress", 0)
                                message_data = data.get("data", {})
                                
                                # 更新进度条
                                progress.update(task, completed=progress_value, description=f"[cyan]{status}")
                                
                                # 如果有消息，显示它
                                if isinstance(message_data, dict) and "message" in message_data:
                                    console.print(f"[yellow]{message_data['message']}[/yellow]")
                                    
                                # 如果分析完成，显示结果
                                if status == "completed" and "results" in message_data:
                                    display_results(message_data["results"])
                            except json.JSONDecodeError:
                                console.print(f"[bold red]无法解析事件数据: {event_data}[/bold red]")
                        
                        # 重置事件缓冲区
                        event_type = None
                        data_buffer = []
                    continue
                
                # 解码行内容
                line = line.decode('utf-8')
                
                # 解析事件类型和数据
                if line.startswith('event:'):
                    event_type = line.split(':', 1)[1].strip()
                elif line.startswith('data:'):
                    data_buffer.append(line.split(':', 1)[1].strip())
            
    except KeyboardInterrupt:
        console.print("[bold yellow]用户中断，正在取消任务...[/bold yellow]")
        cancel_task(task_id)
        
    except Exception as e:
        console.print(f"[bold red]监听事件时发生错误: {str(e)}[/bold red]")

def cancel_task(task_id):
    """取消分析任务"""
    try:
        response = requests.delete(f"http://192.168.31.168:8000/api/analysis/{task_id}")
        if response.status_code == 200:
            console.print(f"[bold yellow]任务 {task_id} 已取消[/bold yellow]")
        else:
            console.print(f"[bold red]取消任务失败: {response.text}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]取消任务时发生错误: {str(e)}[/bold red]")

def display_results(results):
    """显示分析结果"""
    console.print("\n[bold]===== 分析结果 =====")
    
    if not results:
        console.print("[bold red]没有结果数据[/bold red]")
        return
        
    try:
        # 显示决策
        decisions = results.get("decisions", {})
        if decisions:
            console.print(Panel(json.dumps(decisions, indent=2, ensure_ascii=False), 
                               title="交易决策", border_style="green"))
        
        # 显示分析师信号
        analyst_signals = results.get("analyst_signals", {})
        if analyst_signals:
            for analyst, signal in analyst_signals.items():
                console.print(Panel(json.dumps(signal, indent=2, ensure_ascii=False), 
                                   title=f"分析师: {analyst}", border_style="yellow"))
    except Exception as e:
        console.print(f"[bold red]显示结果时发生错误: {str(e)}[/bold red]")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI Hedge Fund API 测试客户端")
    parser.add_argument("--tickers", "-t", nargs="+", required=True, help="要分析的股票代码列表")
    parser.add_argument("--analysts", "-a", nargs="+", help="要使用的分析师列表")
    parser.add_argument("--model", "-m", default="gpt-4o", help="要使用的模型名称")
    parser.add_argument("--provider", "-p", default="OpenAI", help="模型提供商")
    
    args = parser.parse_args()
    
    # 如果没有指定分析师，获取可用的分析师列表
    if not args.analysts:
        available_analysts = get_analysts()
        if not available_analysts:
            console.print("[bold red]无法获取分析师列表，请手动指定分析师[/bold red]")
            return
        args.analysts = [item[1] for item in available_analysts]
    
    # 检查模型是否可用
    available_models = get_models()
    if args.model not in available_models:
        console.print(f"[bold yellow]警告: 模型 {args.model} 不在可用模型列表中，可能会导致错误[/bold yellow]")
    
    # 启动分析任务
    task_id = start_analysis(args.tickers, args.analysts, args.model, args.provider)
    if not task_id:
        return
    
    # 监听事件
    try:
        listen_for_events(task_id)
    except KeyboardInterrupt:
        if TASK_ID:
            cancel_task(TASK_ID)
        console.print("[bold]程序已结束[/bold]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold]程序已结束[/bold]")
        sys.exit(0) 