from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import uuid
import json
import logging
from datetime import datetime

# 导入项目现有的模块
from main import run_hedge_fund
from utils.analysts import ANALYST_ORDER, ANALYST_ID_ORDER
from llm.models import LLM_ORDER, LLM_NAME_ORDER

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Hedge Fund API", description="股票分析实时事件推送API")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置为具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 保存活跃分析任务的状态
# 结构: {task_id: {"status": str, "progress": int, "data": dict, "queue": asyncio.Queue}}
active_tasks = {}

# 定义输入模型
class AnalysisRequest(BaseModel):
    tickers: List[str]
    analysts: List[str]
    model_name: str
    model_provider: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    portfolio: Optional[Dict[str, float]] = None
    show_reasoning: bool = False

# 定义响应模型
class TaskResponse(BaseModel):
    task_id: str
    status: str = "pending"
    
# 分析状态更新函数
async def update_task_status(task_id: str, status: str, progress: int = None, data: Any = None):
    if task_id not in active_tasks:
        return
        
    task_info = active_tasks[task_id]
    task_info["status"] = status
    
    if progress is not None:
        task_info["progress"] = progress
        
    if data is not None:
        task_info["data"] = data
        
    # 将更新推送到事件队列
    await task_info["queue"].put({
        "event": "update",
        "data": {
            "status": status,
            "progress": task_info.get("progress", 0),
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
    })
    
    # 如果状态为完成或失败，添加完成事件
    if status in ["completed", "failed"]:
        await task_info["queue"].put({"event": "end"})

# 执行分析的后台任务
async def run_analysis_task(task_id: str, analysis_request: AnalysisRequest):
    try:
        # 更新状态为处理中
        await update_task_status(task_id, "processing", 10)
        
        # 模拟分析开始阶段
        await asyncio.sleep(1)
        await update_task_status(task_id, "analyzing_data", 20, {"message": "开始分析数据..."})
        
        # 运行实际的分析
        portfolio = analysis_request.portfolio or {}
        start_date = analysis_request.start_date or "2023-01-01"
        end_date = analysis_request.end_date or datetime.now().strftime("%Y-%m-%d")
        
        # 调用分析逻辑的钩子
        await update_task_status(task_id, "running_analysis", 40, {"message": "执行分析师分析..."})
        
        # 异步执行run_hedge_fund
        result = await asyncio.to_thread(
            run_hedge_fund,
            tickers=analysis_request.tickers,
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=analysis_request.show_reasoning,
            selected_analysts=analysis_request.analysts,
            model_name=analysis_request.model_name,
            model_provider=analysis_request.model_provider
        )
        
        # 更新进度和状态
        await update_task_status(task_id, "processing_results", 80, {"message": "处理分析结果..."})
        await asyncio.sleep(1)  # 模拟一些处理时间
        
        # 完成分析
        await update_task_status(task_id, "completed", 100, {"results": result})
        logger.info(f"分析任务 {task_id} 已完成")
        
    except Exception as e:
        logger.error(f"分析任务 {task_id} 执行失败: {str(e)}")
        await update_task_status(task_id, "failed", data={"error": str(e)})
        
    # 清理资源但保留任务数据一段时间
    if task_id in active_tasks:
        # 保留队列和其他数据，但标记为完成
        active_tasks[task_id]["completed"] = True

# 启动新的分析任务
@app.post("/api/analysis", response_model=TaskResponse)
async def start_analysis(analysis_request: AnalysisRequest, background_tasks: BackgroundTasks):
    # 验证输入
    if not analysis_request.tickers:
        raise HTTPException(status_code=400, detail="必须提供至少一个股票代码")
    
    # 验证分析师列表
    for analyst in analysis_request.analysts:
        if analyst not in ANALYST_ID_ORDER:
            raise HTTPException(status_code=400, detail=f"未知分析师: {analyst}")
    
    # 验证模型
    if analysis_request.model_name not in LLM_NAME_ORDER:
        raise HTTPException(status_code=400, detail=f"未支持的模型: {analysis_request.model_name}")
    
    # 创建任务ID
    task_id = str(uuid.uuid4())
    
    # 初始化任务状态
    active_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "data": None,
        "queue": asyncio.Queue(),
        "request": analysis_request.dict(),
        "created_at": datetime.now().isoformat(),
        "completed": False
    }
    
    # 在后台启动分析任务
    background_tasks.add_task(run_analysis_task, task_id, analysis_request)
    
    return {"task_id": task_id, "status": "pending"}

# 获取单个任务的状态
@app.get("/api/analysis/{task_id}")
async def get_task(task_id: str):
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="找不到任务")
    
    task_info = active_tasks[task_id]
    return {
        "task_id": task_id,
        "status": task_info["status"],
        "progress": task_info.get("progress", 0),
        "created_at": task_info["created_at"],
        "completed": task_info.get("completed", False),
        "data": task_info.get("data")
    }

# 获取所有活跃任务
@app.get("/api/analysis")
async def list_tasks():
    return {
        task_id: {
            "status": info["status"],
            "progress": info.get("progress", 0),
            "created_at": info["created_at"],
            "completed": info.get("completed", False)
        }
        for task_id, info in active_tasks.items()
    }

# 获取可用的分析师列表
@app.get("/api/analysts")
async def get_analysts():
    return {"analysts": ANALYST_ORDER}

# 获取可用的模型列表
@app.get("/api/models")
async def get_models():
    return {"models": LLM_ORDER}

# EventSource端点实现
@app.get("/api/events/{task_id}")
async def task_events(request: Request, task_id: str):
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="找不到任务")
    
    async def event_generator():
        queue = active_tasks[task_id]["queue"]
        try:
            # 发送初始状态
            initial_state = {
                "status": active_tasks[task_id]["status"],
                "progress": active_tasks[task_id].get("progress", 0),
                "timestamp": datetime.now().isoformat(),
                "data": active_tasks[task_id].get("data")
            }
            yield {
                "event": "update",
                "data": json.dumps(initial_state)
            }
            
            # 持续发送更新事件
            while True:
                if await request.is_disconnected():
                    logger.info(f"客户端断开连接: {task_id}")
                    break
                
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if event["event"] == "end":
                        yield {
                            "event": "end",
                            "data": ""
                        }
                        break
                    else:
                        yield {
                            "event": event["event"],
                            "data": json.dumps(event["data"])
                        }
                except asyncio.TimeoutError:
                    # 发送保持连接的事件
                    yield {
                        "event": "ping",
                        "data": ""
                    }
                    # 检查任务是否已经完成但是客户端还在等待
                    if active_tasks[task_id].get("completed", False):
                        yield {
                            "event": "end",
                            "data": ""
                        }
                        break
        except Exception as e:
            logger.error(f"事件流错误: {str(e)}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(event_generator())

# 手动关闭任务
@app.delete("/api/analysis/{task_id}")
async def cancel_task(task_id: str):
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="找不到任务")
    
    # 标记任务为取消状态
    await update_task_status(task_id, "cancelled", data={"message": "任务已被手动取消"})
    
    # 添加结束事件
    await active_tasks[task_id]["queue"].put({"event": "end"})
    
    # 标记为完成
    active_tasks[task_id]["completed"] = True
    
    return {"message": "任务已取消", "task_id": task_id}

# 定期清理完成的任务（可以在生产环境中添加一个定时任务）
@app.on_event("startup")
async def startup_event():
    logger.info("AI Hedge Fund API 服务已启动")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 