"""Streamlit web UI for the flight booking agent."""
import os
import streamlit as st
from agent import chat

st.set_page_config(page_title="🛫 AI 机票助手", page_icon="🛫", layout="wide")
st.title("🛫 AI 机票助手")

# ── sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("🛫 机票助手")
    ds = "🟢 DeepSeek" if os.getenv("DEEPSEEK_API_KEY") else "⚪ DeepSeek"
    gf = "🟢 Google Flights" if os.getenv("SERPAPI_API_KEY") else "⚪ Google Flights(模拟)"
    st.caption(f"{ds}　{gf}")

    st.markdown("---")
    st.markdown("**💡 快速示例（点击直接查询）：**")
    for ex in [
        "北京到东京 6月20日 往返",
        "上海飞巴黎 7月初哪天最便宜",
        "深圳到新加坡 单程",
        "北京到纽约 什么时候最划算",
    ]:
        if st.button(ex, use_container_width=True):
            st.session_state.messages = [{"role": "user", "content": ex}]
            st.rerun()

    st.markdown("---")
    if st.button("🧹 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── init messages ────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── render all messages ──────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── handle new input ─────────────────────────────────────────
if prompt := st.chat_input("输入你的旅行需求..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

# Auto-respond if last message is from user
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_msg = st.session_state.messages[-1]["content"]
    # Don't re-render the user message (already shown above)
    with st.chat_message("assistant"):
        with st.spinner("查询中..."):
            try:
                history = st.session_state.messages[:-1]  # 对话历史（不含当前消息）
                response = chat(user_msg, history=history)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"❌ {e}")
