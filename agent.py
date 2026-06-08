"""LangChain agent for flight booking & price analysis."""
import os
from datetime import datetime

from pathlib import Path
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from tools.flight_tools import search_flights, get_cheapest_period, get_airport_info

load_dotenv(Path(__file__).parent / ".env")

def _build_system_prompt() -> str:
    today = datetime.now().strftime("%Y年%m月%d日")
    weekday = ["周一","周二","周三","周四","周五","周六","周日"][datetime.now().weekday()]
    return f"""你是一个专业的机票预订助手。今天是{today}（{weekday}）。

## 核心能力
1. **search_flights_tool** — 搜索航班
2. **get_cheapest_period_tool** — 分析哪天最便宜
3. **get_airport_info_tool** — 查机场代码

## 规则
- 用户说"明天""下周"等模糊时间时，基于今天（{today}）推算具体日期
- 搜索航班时日期必须传 YYYY-MM-DD 格式
- 用户没指定出发地/目的地时，先问清楚
- 拿到结果后，用表格展示，最后给出推荐
- 用中文回复，简洁直接
"""


@tool
def search_flights_tool(origin: str, destination: str, departure_date: str,
                        return_date: str = "", adults: int = 1) -> str:
    """搜索航班。origin/destination 用 IATA 三字码(如PEK,PVG)，departure_date 格式 YYYY-MM-DD，
    return_date 可选（往返票时需要），adults 为成人数。"""
    return search_flights(origin, destination, departure_date, return_date, adults)


@tool
def get_cheapest_period_tool(origin: str, destination: str) -> str:
    """分析某条航线近期哪天最便宜。origin/destination 用 IATA 三字码。"""
    return get_cheapest_period(origin, destination)


@tool
def get_airport_info_tool(city: str) -> str:
    """查询城市的机场代码。city 可以是城市名(如'北京','上海')或 IATA 代码(如'PEK')。"""
    return get_airport_info(city)


def get_agent():
    """Create a fresh agent with current date (not cached, so date stays current)."""
    llm = ChatOpenAI(
        model="deepseek-v4-flash",
        temperature=0.3,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
    )
    tools = [search_flights_tool, get_cheapest_period_tool, get_airport_info_tool]
    return create_agent(llm, tools, system_prompt=_build_system_prompt())


MEMORY_SIZE = 10  # 保留最近 10 条消息（5 轮对话）

def chat(message: str, history: list[dict] | None = None) -> str:
    """Send a message and get the response text.

    Args:
        message: Current user message
        history: List of {"role": "user"|"assistant", "content": "..."}
    """
    agent = get_agent()
    msg_list = []

    # 注入最近历史，让 agent 记住上下文
    if history:
        for m in history[-MEMORY_SIZE:]:
            if m["role"] == "user":
                msg_list.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                msg_list.append(AIMessage(content=m["content"]))

    msg_list.append(HumanMessage(content=message))

    result = agent.invoke(
        {"messages": msg_list},
        config={"recursion_limit": 10},
    )
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return "抱歉，无法处理你的请求，请重试。"
