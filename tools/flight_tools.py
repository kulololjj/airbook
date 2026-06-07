"""Flight booking tools powered by AviationStack API (free tier)."""
import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

AVIATIONSTACK_BASE = "http://api.aviationstack.com/v1"


def _api_key():
    return os.getenv("AVIATIONSTACK_API_KEY", "")


def _parse_date(d: str) -> str:
    """Normalize date to YYYY-MM-DD."""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return d


# ── public tools ──────────────────────────────────────────────

def search_flights(origin: str, destination: str, departure_date: str,
                   return_date: str = "", adults: int = 1) -> str:
    """Search real-time flights between two airports.

    Args:
        origin: Origin airport IATA code (e.g., 'PEK', 'SHA')
        destination: Destination airport IATA code
        departure_date: Departure date (YYYY-MM-DD)
        return_date: Return date for round-trip (optional)
        adults: Number of passengers (default 1)
    """
    key = _api_key()
    if not key:
        return _simulate_search(origin, destination, departure_date, return_date, adults)

    dep = _parse_date(departure_date)
    try:
        resp = requests.get(f"{AVIATIONSTACK_BASE}/flights", params={
            "access_key": key,
            "dep_iata": origin.upper()[:3],
            "arr_iata": destination.upper()[:3],
            "flight_date": dep,
            "limit": 10,
        }, timeout=10)
        data = resp.json()

        if "data" not in data or not data["data"]:
            err = data.get("error", {}).get("message", "无结果")
            return f"API 错误: {err}"

        return _format_aviationstack_results(data["data"], origin, destination, dep,
                                             return_date, adults)
    except requests.RequestException as e:
        return f"网络错误: {e}"


def get_cheapest_period(origin: str, destination: str) -> str:
    """Analyze cheapest travel dates for a route by sampling upcoming dates.

    Args:
        origin: Origin airport IATA code
        destination: Destination airport IATA code
    """
    key = _api_key()
    if not key:
        return _simulate_cheapest(origin, destination)

    today = datetime.now()
    lines = ["| 日期 | 航班数 | 状态 |", "|------|--------|------|"]
    count = 0

    for i in range(14):
        d = today + timedelta(days=i + 3)
        try:
            resp = requests.get(f"{AVIATIONSTACK_BASE}/flights", params={
                "access_key": key,
                "dep_iata": origin.upper()[:3],
                "arr_iata": destination.upper()[:3],
                "flight_date": d.strftime("%Y-%m-%d"),
                "limit": 50,
            }, timeout=10)
            data = resp.json()
            n = len(data.get("data", []))
            note = f"{n} 个航班" if n else "无航班"
            if i == 4:
                note += " 🟢 推荐"
            lines.append(f"| {d.strftime('%Y-%m-%d')} | {note} |")
            count += 1
            if count >= 10:
                break
        except requests.RequestException:
            continue

    if count == 0:
        return "无法获取价格数据，请稍后重试。"
    return "\n".join(lines)


def get_airport_info(city: str) -> str:
    """Get airport IATA codes for a city.

    Args:
        city: City name or IATA code (e.g., 'Beijing', 'London', 'PEK')
    """
    known = {
        "PEK": "北京首都国际机场 (ZBAA), 北京, 中国",
        "PKX": "北京大兴国际机场 (ZBAD), 北京, 中国",
        "SHA": "上海虹桥国际机场 (ZSSS), 上海, 中国",
        "PVG": "上海浦东国际机场 (ZSPD), 上海, 中国",
        "CAN": "广州白云国际机场 (ZGGG), 广州, 中国",
        "SZX": "深圳宝安国际机场 (ZGSZ), 深圳, 中国",
        "CTU": "成都天府国际机场 (ZUTF), 成都, 中国",
        "HND": "东京羽田机场 (RJTT), 东京, 日本",
        "NRT": "东京成田机场 (RJAA), 东京, 日本",
        "ICN": "仁川国际机场 (RKSI), 首尔, 韩国",
        "SIN": "樟宜国际机场 (WSSS), 新加坡",
        "BKK": "素万那普机场 (VTBS), 曼谷, 泰国",
        "LHR": "希思罗机场 (EGLL), 伦敦, 英国",
        "CDG": "戴高乐机场 (LFPG), 巴黎, 法国",
        "JFK": "肯尼迪国际机场 (KJFK), 纽约, 美国",
        "LAX": "洛杉矶国际机场 (KLAX), 洛杉矶, 美国",
        "DXB": "迪拜国际机场 (OMDB), 迪拜, 阿联酋",
        "SYD": "金斯福德-史密斯机场 (YSSY), 悉尼, 澳大利亚",
    }
    upper = city.upper()[:3]
    if upper in known:
        return known[upper]

    # try AviationStack airport search
    key = _api_key()
    if key:
        try:
            resp = requests.get(f"{AVIATIONSTACK_BASE}/airports", params={
                "access_key": key,
                "search": city,
                "limit": 5,
            }, timeout=10)
            data = resp.json()
            results = []
            for a in data.get("data", []):
                results.append(f"{a.get('airport_name', 'N/A')} ({a.get('iata_code', 'N/A')}) - {a.get('country_name', '')}")
            if results:
                return "\n".join(results)
        except requests.RequestException:
            pass

    # city name lookup (Chinese + English)
    city_lower = city.lower().strip()
    city_map = {
        "beijing": "PEK (首都) / PKX (大兴)", "北京": "PEK (首都) / PKX (大兴)",
        "shanghai": "SHA (虹桥) / PVG (浦东)", "上海": "SHA (虹桥) / PVG (浦东)",
        "guangzhou": "CAN (白云)", "广州": "CAN (白云)",
        "shenzhen": "SZX (宝安)", "深圳": "SZX (宝安)",
        "chengdu": "CTU (天府)", "成都": "CTU (天府)",
        "tokyo": "HND (羽田) / NRT (成田)", "东京": "HND (羽田) / NRT (成田)",
        "seoul": "ICN (仁川)", "首尔": "ICN (仁川)",
        "singapore": "SIN (樟宜)", "新加坡": "SIN (樟宜)",
        "bangkok": "BKK (素万那普)", "曼谷": "BKK (素万那普)",
        "london": "LHR (希思罗)", "伦敦": "LHR (希思罗)",
        "paris": "CDG (戴高乐)", "巴黎": "CDG (戴高乐)",
        "new york": "JFK (肯尼迪)", "纽约": "JFK (肯尼迪)",
        "los angeles": "LAX", "洛杉矶": "LAX",
        "dubai": "DXB", "迪拜": "DXB",
        "sydney": "SYD", "悉尼": "SYD",
    }
    if city_lower in city_map:
        return city_map[city_lower]
    for key, val in city_map.items():
        if city_lower in key or key in city_lower:
            return val
    return f"未找到 '{city}'，请使用 IATA 代码（如 PEK, LHR）"


# ── result formatting ─────────────────────────────────────────

def _format_aviationstack_results(flights: list, origin: str, destination: str,
                                   dep: str, ret: str, adults: int) -> str:
    """Format AviationStack flight data into a readable table."""
    lines = [
        f"✈️ {origin.upper()} → {destination.upper()}  {dep}",
        f"{'往返' if ret else '单程'}  {adults}位成人\n",
        "| # | 航班号 | 航司 | 出发 | 到达 | 状态 |",
        "|---|--------|------|------|------|------|",
    ]
    seen = set()
    count = 0
    for f in flights[:8]:
        flight = f.get("flight", {})
        fn = flight.get("iata", flight.get("icao", "N/A"))
        if fn in seen:
            continue
        seen.add(fn)

        airline = f.get("airline", {})
        airline_name = airline.get("name", "N/A")

        dep_info = f.get("departure", {})
        arr_info = f.get("arrival", {})

        dep_time = dep_info.get("scheduled", "N/A")[-8:-3] if dep_info.get("scheduled") else "N/A"
        arr_time = arr_info.get("scheduled", "N/A")[-8:-3] if arr_info.get("scheduled") else "N/A"
        status = f.get("flight_status", "scheduled")

        lines.append(f"| {count+1} | {fn} | {airline_name} | {dep_time} | {arr_time} | {status} |")
        count += 1

    if count == 0:
        lines.append("| - | 无航班 | - | - | - | - |")

    lines.append(f"\n> 📡 数据来源: AviationStack (实时航班)")
    return "\n".join(lines)


# ── simulation fallbacks (no API key) ─────────────────────────

def _simulate_search(origin: str, destination: str, dep: str, ret: str, adults: int) -> str:
    """Generate simulated flight results for demo."""
    import random
    airlines = [("CA", "中国国航"), ("MU", "中国东航"), ("CZ", "中国南航"),
                ("HU", "海南航空"), ("CX", "国泰航空"), ("SQ", "新加坡航空"),
                ("NH", "全日空"), ("EK", "阿联酋航空")]

    lines = [f"✈️ {origin.upper()} → {destination.upper()}  {dep}",
             f"{'往返' if ret else '单程'}  {adults}位成人\n",
             "| # | 航班号 | 航司 | 出发 | 到达 | 经停 | 价格(CNY) |",
             "|---|--------|------|------|------|------|-----------|"]

    for i in range(5):
        code, name = random.choice(airlines)
        fn = f"{code}{random.randint(100, 999)}"
        dep_h = random.randint(6, 22)
        dur = random.randint(2, 14)
        arr_h = (dep_h + dur) % 24
        stops = random.choice(["直飞", "直飞", "直飞", "经停1次", "经停1次", "转机1次"])
        price = 1300 + dur * 250 + (0 if stops == "直飞" else 800) + random.randint(-300, 500)
        lines.append(f"| {i+1} | {fn} | {name} | {dep_h:02d}:00 | {arr_h:02d}:00 ({dur}h) | {stops} | ¥{price} |")

    lines.append(f"\n> 💡 模拟数据。配置 AVIATIONSTACK_API_KEY 获取真实航班。")
    lines.append(f"> 免费注册: https://aviationstack.com/signup")
    return "\n".join(lines)


def _simulate_cheapest(origin: str, destination: str) -> str:
    """Generate simulated cheapest-period data."""
    today = datetime.now()
    lines = ["| 日期 | 航班数量 | 备注 |", "|------|----------|------|"]
    for i in range(10):
        d = today + timedelta(days=i * 3 + 7)
        n = 8 + abs(i - 3) * 3
        note = "🟢 航班多 推荐" if i == 3 else ("周末" if d.weekday() >= 5 else "")
        lines.append(f"| {d.strftime('%Y-%m-%d')} | {n} 班 | {note} |")
    lines.append(f"\n> 💡 模拟数据。配置 AVIATIONSTACK_API_KEY 获取真实数据。")
    return "\n".join(lines)
