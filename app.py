"""
app.py — Streamlit 前端界面
运行：streamlit run app.py
"""

import streamlit as st
from qa import answer, get_retriever

# ── 页面配置 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="达利欧 AI 投资顾问",
    page_icon="📈",
    layout="centered",
)

st.title("📈 达利欧 AI 投资顾问")
st.caption("基于瑞·达利欧《原则》《债务危机》《变化中的世界秩序》等著作")

st.warning(
    "⚠️ 本工具仅供学习参考，不构成任何投资建议。投资有风险，决策需谨慎。",
    icon="⚠️",
)

# ── 初始化 Session State ──────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "sources_history" not in st.session_state:
    st.session_state.sources_history = []

if "collection" not in st.session_state:
    with st.spinner("正在加载知识库..."):
        try:
            st.session_state.collection = get_retriever()
            st.success("✅ 知识库加载完成", icon="✅")
        except RuntimeError as e:
            st.error(f"❌ {e}")
            st.stop()

# ── 侧边栏 ───────────────────────────────────────────────────
with st.sidebar:
    st.header("💡 关于本工具")
    st.markdown(
        """
        本工具基于 **RAG（检索增强生成）** 技术：

        1. 将达利欧书籍切分为知识片段
        2. 根据你的问题检索最相关内容
        3. 由 **MiniMax AI** 结合达利欧理论生成回答

        **适合问的问题：**
        - 如何应对经济下行周期？
        - 达利欧如何看待债务危机？
        - 什么是全天候投资组合？
        - 如何分散投资以降低风险？
        - 美元霸权衰退会有哪些影响？
        """
    )
    st.divider()
    if st.button("🗑️ 清空对话历史", use_container_width=True):
        st.session_state.messages = []
        st.session_state.sources_history = []
        st.rerun()

    st.caption("Powered by MiniMax & ChromaDB")

# ── 显示历史消息 ──────────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # 在 assistant 消息下显示参考来源
        if msg["role"] == "assistant" and i // 2 < len(st.session_state.sources_history):
            sources = st.session_state.sources_history[i // 2]
            if sources:
                with st.expander("📚 查看参考来源", expanded=False):
                    for j, s in enumerate(sources[:4], 1):
                        st.markdown(
                            f"**{j}.** 《{s['book']}》第 {s['page']} 页  "
                            f"（相关度：{s['score']}）\n\n"
                            f"> {s['text'][:150]}..."
                        )

# ── 用户输入 ──────────────────────────────────────────────────
if prompt := st.chat_input("请输入你的投资问题，例如：如何在债务危机中保护资产？"):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 生成回答
    with st.chat_message("assistant"):
        with st.spinner("正在检索达利欧的理论并思考..."):
            try:
                # 构建对话历史（只传 role 和 content）
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]  # 不含刚刚加入的用户消息
                ]

                reply, sources = answer(
                    question=prompt,
                    history=history,
                    collection=st.session_state.collection,
                )

                st.markdown(reply)

                # 显示来源
                if sources:
                    with st.expander("📚 查看参考来源", expanded=False):
                        for j, s in enumerate(sources[:4], 1):
                            st.markdown(
                                f"**{j}.** 《{s['book']}》第 {s['page']} 页  "
                                f"（相关度：{s['score']}）\n\n"
                                f"> {s['text'][:150]}..."
                            )

                # 保存到历史
                st.session_state.messages.append(
                    {"role": "assistant", "content": reply}
                )
                st.session_state.sources_history.append(sources)

            except ValueError as e:
                st.error(f"配置错误：{e}")
            except Exception as e:
                st.error(f"出现错误：{e}")
