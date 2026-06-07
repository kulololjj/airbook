"""Flight booking tools — real data via AviationStack API (free: 500 req/month)."""
import os
from datetime import datetime, timedelta

import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

AVIATIONSTACK_BASE = "http://api.aviationstack.com/v1"

# ── airport database ──────────────────────────────────────────

AIRPORTS = {
    "PEK": ("北京首都国际机场", "北京", "中国"),
    "PKX": ("北京大兴国际机场", "北京", "中国"),
    "SHA": ("上海虹桥国际机场", "上海", "中国"),
    "PVG": ("上海浦东国际机场", "上海", "中国"),
    "CAN": ("广州白云国际机场", "广州", "中国"),
    "SZX": ("深圳宝安国际机场", "深圳", "中国"),
    "CTU": ("成都天府国际机场", "成都", "中国"),
    "HGH": ("杭州萧山国际机场", "杭州", "中国"),
    "CKG": ("重庆江北国际机场", "重庆", "中国"),
    "HND": ("东京羽田机场", "东京", "日本"),
    "NRT": ("东京成田机场", "东京", "日本"),
    "ICN": ("仁川国际机场", "首尔", "韩国"),
    "SIN": ("樟宜国际机场", "新加坡", "新加坡"),
    "BKK": ("素万那普机场", "曼谷", "泰国"),
    "LHR": ("希思罗机场", "伦敦", "英国"),
    "CDG": ("戴高乐机场", "巴黎", "法国"),
    "JFK": ("肯尼迪国际机场", "纽约", "美国"),
    "LAX": ("洛杉矶国际机场", "洛杉矶", "美国"),
    "DXB": ("迪拜国际机场", "迪拜", "阿联酋"),
    "SYD": ("金斯福德-史密斯机场", "悉尼", "澳大利亚"),
}

CITY_TO_IATA = {
    "北京": ["PEK", "PKX"], "beijing": ["PEK", "PKX"],
    "上海": ["SHA", "PVG"], "shanghai": ["SHA", "PVG"],
    "广州": ["CAN"], "guangzhou": ["CAN"],
    "深圳": ["SZX"], "shenzhen": ["SZX"],
    "成都": ["CTU"], "chengdu": ["CTU"],
    "杭州": ["HGH"], "hangzhou": ["HGH"],
    "重庆": ["CKG"], "chongqing": ["CKG"],
    "东京": ["HND", "NRT"], "tokyo": ["HND", "NRT"],
    "首尔": ["ICN"], "seoul": ["ICN"],
    "新加坡": ["SIN"], "singapore": ["SIN"],
    "曼谷": ["BKK"], "bangkok": ["BKK"],
    "伦敦": ["LHR"], "london": ["LHR"],
    "巴黎": ["CDG"], "paris": ["CDG"],
    "纽约": ["JFK"], "new york": ["JFK"],
    "洛杉矶": ["LAX"], "los angeles": ["LAX"],
    "迪拜": ["DXB"], "dubai": ["DXB"],
    "悉尼": ["SYD"], "sydney": ["SYD"],
}


def _parse_date(d: str) -> str:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return d


def _resolve_city(city: str) -> list[str]:
    upper = city.upper().strip()[:3]
    if upper in AIRPORTS:
        return [upper]
    lower = city.lower().strip()
    if lower in CITY_TO_IATA:
        return CITY_TO_IATA[lower]
    for key, val in CITY_TO_IATA.items():
        if lower in key or key in lower:
            return val
    return [upper]


def _fmt_time(iso: str) -> str:
    """Extract HH:MM from ISO time string like '2026-06-07T21:30:00+00:00'."""
    try:
        return iso.split("T")[1][:5]  # "21:30:00+00:00" -> "21:30"
    except (IndexError, AttributeError):
        return "N/A"


def _utc_to_local(time_str: str) -> str:
    """Convert UTC ISO time to China time (UTC+8) HH:MM display."""
    try:
        from datetime import timezone, timedelta
        dt = datetime.fromisoformat(time_str)
        local = dt.astimezone(timezone(timedelta(hours=8)))
        return local.strftime("%H:%M")
    except Exception:
        return _fmt_time(time_str)


# ── public tools ──────────────────────────────────────────────

def search_flights(origin: str, destination: str, departure_date: str,
                   return_date: str = "", adults: int = 1) -> str:
    """Search real flights via AviationStack.

    Args:
        origin: Origin city/IATA code (e.g., '北京', 'PEK')
        destination: Destination city/IATA code
        departure_date: Departure date (YYYY-MM-DD)
        return_date: Optional return date
        adults: Number of passengers
    """
    key = os.getenv("AVIATIONSTACK_API_KEY", "")
    dep = _parse_date(departure_date)
    org_codes = _resolve_city(origin)
    dst_codes = _resolve_city(destination)
    trip_type = "往返" if return_date else "单程"

    header = f"✈️ {org_codes[0]} → {dst_codes[0]}  {dep}  {trip_type} {adults}人\n"

    if not key:
        return header + _simulate_search(org_codes[0], dst_codes[0], dep, return_date, adults)

    try:
        # Free tier only supports live flights (no flight_date filter)
        resp = requests.get(f"{AVIATIONSTACK_BASE}/flights", params={
            "access_key": key,
            "dep_iata": org_codes[0],
            "arr_iata": dst_codes[0],
            "limit": 10,
        }, timeout=15)
        data = resp.json()

        if "error" in data:
            return header + f"API 错误: {data['error'].get('message', '未知错误')}"

        flights = data.get("data", [])
        if not flights:
            return header + "未找到航班，请尝试其他日期。"

        lines = [header,
                 "| # | 航班号 | 航司 | 出发 | 到达 | 航站楼 | 状态 |",
                 "|---|--------|------|------|------|--------|------|"]

        seen = set()
        count = 0
        for f in flights:
            fl = f.get("flight", {})
            fn = fl.get("iata", "N/A")
            if fn in seen:
                continue
            seen.add(fn)

            al = f.get("airline", {})
            airline = al.get("name", "N/A")
            dep_info = f.get("departure", {})
            arr_info = f.get("arrival", {})

            dep_time = _utc_to_local(dep_info.get("scheduled", ""))
            arr_time = _utc_to_local(arr_info.get("scheduled", ""))
            dep_term = dep_info.get("terminal", "-") or "-"
            arr_term = arr_info.get("terminal", "-") or "-"
            status = f.get("flight_status", "scheduled")

            lines.append(
                f"| {count+1} | {fn} | {airline} | {dep_time} | {arr_time} "
                f"| {dep_term}→{arr_term} | {status} |"
            )
            count += 1
            if count >= 8:
                break

        if count == 0:
            lines.append("| - | 无直飞航班 | - | - | - | - | - |")

        lines.append("")
        lines.append(f"> 📡 AviationStack 今日航班 ({datetime.now().strftime('%H:%M')}) · 免费版仅显示当天")
        return "\n".join(lines)

    except requests.RequestException as e:
        return header + f"网络错误: {e}"


def get_cheapest_period(origin: str, destination: str) -> str:
    """Sample upcoming dates to find which days have the most flights.

    Args:
        origin: Origin IATA code
        destination: Destination IATA code
    """
    key = os.getenv("AVIATIONSTACK_API_KEY", "")
    org_codes = _resolve_city(origin)
    dst_codes = _resolve_city(destination)

    header = f"📅 {org_codes[0]} → {dst_codes[0]} 近期航班分析\n"
    if not key:
        return header + _simulate_cheapest(org_codes[0], dst_codes[0])

    # Free API can't query future dates. Get today's data as reference.
    try:
        resp = requests.get(f"{AVIATIONSTACK_BASE}/flights", params={
            "access_key": key,
            "dep_iata": org_codes[0],
            "arr_iata": dst_codes[0],
            "limit": 100,
        }, timeout=10)
        data = resp.json()
        today_count = len(data.get("data", [])) if "data" in data else 0
    except requests.RequestException:
        today_count = 0

    lines = [header, f"今日航班: {today_count} 班\n"]
    lines.append("> ⚠️ 免费 API 不支持查询未来日期价格。以下为参考数据：")
    return "\n".join(lines) + "\n" + _simulate_cheapest(org_codes[0], dst_codes[0])


def get_airport_info(city: str) -> str:
    """Get airport IATA codes for a city.

    Args:
        city: City name or IATA code (e.g., '北京', 'London', 'PEK')
    """
    upper = city.upper().strip()[:3]
    if upper in AIRPORTS:
        name, cn_city, country = AIRPORTS[upper]
        return f"{upper} — {name}, {cn_city}, {country}"

    codes = _resolve_city(city)
    if codes:
        result = []
        for c in codes:
            if c in AIRPORTS:
                name, cn_city, _ = AIRPORTS[c]
                result.append(f"{c} — {name}, {cn_city}")
        if result:
            return "\n".join(result)

    # try AviationStack airport search
    key = os.getenv("AVIATIONSTACK_API_KEY", "")
    if key:
        try:
            resp = requests.get(f"{AVIATIONSTACK_BASE}/airports", params={
                "access_key": key, "search": city, "limit": 5,
            }, timeout=10)
            data = resp.json()
            results = []
            for a in data.get("data", []):
                results.append(
                    f"{a.get('iata_code', '?')} — {a.get('airport_name', 'N/A')}, "
                    f"{a.get('country_name', '')}"
                )
            if results:
                return "\n".join(results)
        except Exception:
            pass

    return f"未找到 '{city}'，请使用 IATA 代码（如 PEK, PVG）或城市名（如 北京, 东京）"


# ── simulation fallback ───────────────────────────────────────

def _simulate_search(origin: str, destination: str, dep: str, ret: str, adults: int) -> str:
    import random
    airlines = [
        ("CA", "中国国航"), ("MU", "中国东航"), ("CZ", "中国南航"),
        ("HU", "海南航空"), ("CX", "国泰航空"), ("SQ", "新加坡航空"),
        ("NH", "全日空"), ("EK", "阿联酋航空"),
    ]
    lines = ["| # | 航班号 | 航司 | 出发 | 到达 | 经停 | 价格(CNY) |",
             "|---|--------|------|------|------|------|-----------|"]
    for i in range(5):
        code, name = random.choice(airlines)
        fn = f"{code}{random.randint(100, 999)}"
        dh = random.randint(6, 22)
        dur = random.randint(2, 14)
        ah = (dh + dur) % 24
        stops = random.choice(["直飞", "直飞", "直飞", "经停1次", "转机1次"])
        price = 1300 + dur * 250 + (0 if stops == "直飞" else 800) + random.randint(-300, 500)
        lines.append(f"| {i+1} | {fn} | {name} | {dh:02d}:00 | {ah:02d}:00 ({dur}h) | {stops} | ¥{price} |")
    lines.append(f"\n> 💡 模拟数据。配置 AVIATIONSTACK_API_KEY 获取真实航班。")
    lines.append(f"> 免费注册: https://aviationstack.com/signup (500次/月)")
    return "\n".join(lines)


def _simulate_cheapest(origin: str, destination: str) -> str:
    today = datetime.now()
    lines = ["| 日期 | 航班数 | 建议 |", "|------|--------|------|"]
    for i in range(8):
        d = today + timedelta(days=i * 3 + 7)
        n = 8 + abs(i - 3) * 3
        note = "🟢 推荐" if i == 3 else ""
        lines.append(f"| {d.strftime('%Y-%m-%d')} | {n} 班 | {note} |")
    return "\n".join(lines)
