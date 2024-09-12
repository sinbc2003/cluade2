import streamlit as st
from anthropic import Anthropic
import os

# Streamlit 페이지 설정
st.set_page_config(page_title="Claude Chatbot", page_icon=":robot_face:")

# API 키 가져오기
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    st.error("ANTHROPIC_API_KEY가 설정되지 않았습니다. Streamlit Cloud의 환경 변수를 확인해주세요.")
    st.stop()

# Anthropic 클라이언트 설정
try:
    client = Anthropic(api_key=api_key)
except Exception as e:
    st.error(f"Anthropic 클라이언트 초기화 중 오류가 발생했습니다: {str(e)}")
    st.stop()

# 시스템 메시지 설정
SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."

# 세션 상태 초기화 및 기존 메시지 업데이트
if "messages" not in st.session_state:
    st.session_state.messages = []

# 채팅 인터페이스
st.title("Claude Chatbot")

# 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("무엇을 도와드릴까요?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            # Claude API를 사용하여 응답 생성
            stream = client.messages.stream(
                max_tokens=1000,
                messages=st.session_state.messages,
                model="claude-3-sonnet-20240229",
                system=SYSTEM_MESSAGE,
            )

            for chunk in stream:
                if chunk.type == "content_block_start":
                    continue
                elif chunk.type == "content_block_delta":
                    full_response += chunk.delta.text
                    message_placeholder.markdown(full_response + "▌")
                elif chunk.type == "content_block_stop":
                    message_placeholder.markdown(full_response)
                elif chunk.type == "message_stop":
                    break

        except Exception as e:
            st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")
        
    if full_response:
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# 디버그 정보 표시
st.sidebar.title("디버그 정보")
st.sidebar.json(st.session_state.messages)
st.sidebar.text(f"System Message: {SYSTEM_MESSAGE}")
