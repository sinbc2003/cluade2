import streamlit as st
import anthropic

# Streamlit 페이지 설정
st.set_page_config(page_title="Claude Chatbot", page_icon=":robot_face:")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# Anthropic 클라이언트 설정
client = anthropic.Anthropic()

# 채팅 인터페이스
st.title("Claude Chatbot")

# 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("무엇을 도와드릴까요?"):
    st.session_state.messages.append({"role": "human", "content": prompt})
    with st.chat_message("human"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # Claude API를 사용하여 응답 생성
        for response in client.messages.stream(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]
        ):
            full_response += (response.delta.text or "")
            message_placeholder.markdown(full_response + "▌")
        
        message_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})
