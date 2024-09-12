import streamlit as st
from anthropic import Anthropic
import os
import google.generativeai as genai
import openai
import re

# Streamlit 페이지 설정
st.set_page_config(page_title="Multi-Model Chatbot", page_icon=":robot_face:")

# API 키 가져오기
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not (ANTHROPIC_API_KEY and OPENAI_API_KEY and GEMINI_API_KEY):
    st.error("하나 이상의 API 키가 설정되지 않았습니다. Streamlit Cloud의 환경 변수를 확인해주세요.")
    st.stop()

# API 클라이언트 설정
try:
    anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"API 클라이언트 초기화 중 오류가 발생했습니다: {str(e)}")
    st.stop()

# 모델 선택 드롭다운
MODEL_OPTIONS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gemini-pro",
    "gemini-1.5-flash",
    "claude-3-5-sonnet-20240620"
]
selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)

# 시스템 메시지 설정
SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 이미지 생성 관련 키워드
IMAGE_KEYWORDS = ["이미지", "사진", "그림", "그려"]

# 이미지 생성 요청 확인 함수
def is_image_request(text):
    return any(keyword in text for keyword in IMAGE_KEYWORDS)

# DALL-E를 사용한 이미지 생성 함수
def generate_image(prompt):
    try:
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url
    except Exception as e:
        st.error(f"이미지 생성 중 오류가 발생했습니다: {str(e)}")
        return None

# 채팅 인터페이스
st.title("Multi-Model Chatbot")

# 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and "image_url" in message:
            st.image(message["image_url"], caption="생성된 이미지")
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("무엇을 도와드릴까요?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        if is_image_request(prompt):
            message_placeholder.markdown("이미지를 생성하겠습니다. 잠시만 기다려 주세요.")
            image_url = generate_image(prompt)
            if image_url:
                st.image(image_url, caption="생성된 이미지")
                full_response = "요청하신 이미지를 생성했습니다. 위의 이미지를 확인해 주세요."
                st.session_state.messages.append({"role": "assistant", "content": full_response, "image_url": image_url})
            else:
                full_response = "죄송합니다. 이미지 생성 중 오류가 발생했습니다."
        else:
            try:
                if "gpt" in selected_model:
                    response = openai_client.chat.completions.create(
                        model=selected_model,
                        messages=[{"role": "system", "content": SYSTEM_MESSAGE}] + st.session_state.messages,
                        stream=True
                    )
                    for chunk in response:
                        if chunk.choices[0].delta.content is not None:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                elif "gemini" in selected_model:
                    model = genai.GenerativeModel(selected_model)
                    response = model.generate_content(prompt, stream=True)
                    for chunk in response:
                        if chunk.text:
                            full_response += chunk.text
                            message_placeholder.markdown(full_response + "▌")
                elif "claude" in selected_model:
                    with anthropic_client.messages.stream(
                        max_tokens=1000,
                        messages=st.session_state.messages,
                        model=selected_model,
                        system=SYSTEM_MESSAGE,
                    ) as stream:
                        for text in stream.text_stream:
                            full_response += text
                            message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
            except Exception as e:
                st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")
        
        if full_response and not is_image_request(prompt):
            st.session_state.messages.append({"role": "assistant", "content": full_response})

# 디버그 정보 표시
st.sidebar.title("디버그 정보")
st.sidebar.json(st.session_state.messages)
st.sidebar.text(f"System Message: {SYSTEM_MESSAGE}")
st.sidebar.text(f"Selected Model: {selected_model}")
