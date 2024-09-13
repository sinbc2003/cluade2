import streamlit as st
from anthropic import Anthropic
import os
from openai import OpenAI
import google.generativeai as genai
import re
import requests
from pymongo import MongoClient
from bson.objectid import ObjectId
import urllib.parse

# 전역 변수로 db 선언
db = None

# Streamlit 페이지 설정
st.set_page_config(page_title="Chatbot Platform", page_icon=":robot_face:", layout="wide")

# MongoDB 연결
try:
    MONGO_URI = st.secrets["MONGO_URI"]
    client = MongoClient(MONGO_URI)
    db = client.get_database("chatbot_platform")  # 또는 실제 사용하려는 DB 이름
except Exception as e:
    st.error("데이터베이스 연결에 실패했습니다. 관리자에게 문의해주세요.")
    db = None

# Google Apps Script 웹 앱 URL
GOOGLE_APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx2gynWGYXtmYH3V0mIYqkZolC9Nbt5HwUVtFMChmgqBUqasSSZvulcTPTVVFzFy0gy/exec"

# API 키 가져오기
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

if not (ANTHROPIC_API_KEY and OPENAI_API_KEY and GEMINI_API_KEY):
    st.error("하나 이상의 API 키가 설정되지 않았습니다. Streamlit Cloud의 환경 변수를 확인해주세요.")
    st.stop()

# API 클라이언트 설정
try:
    anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("API 클라이언트 초기화에 실패했습니다. 관리자에게 문의해주세요.")
    st.stop()

# 모델 선택 드롭다운
MODEL_OPTIONS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gemini-pro",
    "gemini-1.5-pro-latest",
    "claude-3-opus-20240229"
]

# 시스템 메시지 설정
SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."

# 이미지 생성 관련 키워드와 패턴
IMAGE_PATTERNS = [
    r'(이미지|그림|사진|웹툰).*?(그려|만들어|생성|출력)',
    r'(그려|만들어|생성|출력).*?(이미지|그림|사진|웹툰)',
    r'(시각화|시각적).*?(표현|묘사)',
    r'비주얼.*?(만들어|생성)',
    r'(그려|만들어|생성|출력)[줘라]',
    r'(이미지|그림|사진|웹툰).*?(보여)',
]

# 이미지 생성 요청 확인 함수
def is_image_request(text):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in IMAGE_PATTERNS)

# DALL-E를 사용한 이미지 생성 함수
def generate_image(prompt):
    try:
        clean_prompt = re.sub(r'(이미지|그림|사진|웹툰).*?(그려|만들어|생성|출력|보여)[줘라]?', '', prompt).strip()
        safe_prompt = f"Create a safe and appropriate image based on this description: {clean_prompt}. The image should be family-friendly and avoid any controversial or sensitive content."
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=safe_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url
    except Exception as e:
        st.error("이미지 생성에 실패했습니다. 다시 시도해주세요.")
        return None

# 로그인 함수
def login(username, password):
    params = {
        "action": "login",
        "username": username,
        "password": password
    }
    try:
        response = requests.get(GOOGLE_APPS_SCRIPT_URL, params=params, timeout=10)
        if response.text.strip().lower() == "true":
            if db is not None:
                user = db.users.find_one({"username": username})
                if not user:
                    new_user = {"username": username, "chatbots": []}
                    result = db.users.insert_one(new_user)
                    user = db.users.find_one({"_id": result.inserted_id})
                return user
            else:
                st.warning("데이터베이스 연결이 없습니다. 임시 사용자 데이터를 사용합니다.")
                return {"username": username, "chatbots": []}
        return None
    except requests.RequestException as e:
        st.error("로그인 요청 중 오류가 발생했습니다. 다시 시도해주세요.")
        return None

# 로그인 페이지
def show_login_page():
    st.title("로그인")
    username = st.text_input("아이디")
    password = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        with st.spinner("로그인 중..."):
            user = login(username, password)
            if user:
                st.session_state.user = user
                st.session_state.current_page = 'home'
                st.success("로그인 성공!")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 잘못되었습니다.")

# 홈 페이지 (기본 챗봇)
def show_home_page():
    st.title("기본 챗봇")
    selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)
    
    if 'home_messages' not in st.session_state:
        st.session_state.home_messages = []
    
    for message in st.session_state.home_messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "image_url" in message:
                st.image(message["image_url"], caption="생성된 이미지")
            st.markdown(message["content"])

    if prompt := st.chat_input("무엇을 도와드릴까요?"):
        st.session_state.home_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            if is_image_request(prompt):
                message_placeholder.markdown("이미지를 생성하겠습니다. 잠시만 기다려 주세요.")
                with st.spinner("이미지 생성 중..."):
                    image_url = generate_image(prompt)
                    if image_url:
                        st.image(image_url, caption="생성된 이미지")
                        full_response = "요청하신 이미지를 생성했습니다. 위의 이미지를 확인해 주세요."
                        st.session_state.home_messages.append({"role": "assistant", "content": full_response, "image_url": image_url})
                    else:
                        full_response = "죄송합니다. 이미지 생성 중 오류가 발생했습니다. 다른 주제로 시도해 보시거나, 요청을 더 구체적으로 해주세요."
            else:
                try:
                    if "gpt" in selected_model:
                        response = openai_client.chat.completions.create(
                            model=selected_model,
                            messages=[{"role": "system", "content": SYSTEM_MESSAGE}] + st.session_state.home_messages,
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
                            messages=st.session_state.home_messages,
                            model=selected_model,
                            system=SYSTEM_MESSAGE,
                        ) as stream:
                            for text in stream.text_stream:
                                full_response += text
                                message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    st.error("응답 생성 중 오류가 발생했습니다. 다시 시도해주세요.")
            
            if full_response:
                st.session_state.home_messages.append({"role": "assistant", "content": full_response})

    if st.button("대화 내역 초기화"):
        st.session_state.home_messages = []
        st.rerun()

# 새 챗봇 만들기 페이지
def show_create_chatbot_page():
    st.title("새 챗봇 만들기")
    chatbot_name = st.text_input("챗봇 이름")
    chatbot_description = st.text_area("챗봇 설명")
    if st.button("챗봇 생성"):
        new_chatbot = {
            "name": chatbot_name,
            "description": chatbot_description,
            "messages": []
        }
        if db is not None:  # 여기를 수정했습니다
            try:
                db.users.update_one(
                    {"_id": st.session_state.user["_id"]},
                    {"$push": {"chatbots": new_chatbot}}
                )
                st.session_state.user = db.users.find_one({"_id": st.session_state.user["_id"]})
                st.success(f"'{chatbot_name}' 챗봇이 생성되었습니다!")
            except Exception as e:
                st.error(f"챗봇 생성 중 오류가 발생했습니다: {str(e)}")
        else:
            if 'chatbots' not in st.session_state.user:
                st.session_state.user['chatbots'] = []
            st.session_state.user['chatbots'].append(new_chatbot)
            st.success(f"'{chatbot_name}' 챗봇이 생성되었습니다! (오프라인 모드)")

# 사용 가능한 챗봇 페이지
def show_available_chatbots_page():
    st.title("사용 가능한 챗봇")
    for i, chatbot in enumerate(st.session_state.user["chatbots"]):
        st.write(f"{i+1}. {chatbot['name']}")
        st.write(chatbot['description'])
        if st.button(f"사용하기 #{i}"):
            st.session_state.current_chatbot = i
            st.session_state.current_page = 'chatbot'
            st.rerun()

# 특정 챗봇 페이지
def show_chatbot_page():
    chatbot = st.session_state.user["chatbots"][st.session_state.current_chatbot]
    st.title(f"{chatbot['name']} 챗봇")
    selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)
    
    for message in chatbot['messages']:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "image_url" in message:
                st.image(message["image_url"], caption="생성된 이미지")
            st.markdown(message["content"])

    if prompt := st.chat_input("무엇을 도와드릴까요?"):
        chatbot['messages'].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            if is_image_request(prompt):
                message_placeholder.markdown("이미지를 생성하겠습니다. 잠시만 기다려 주세요.")
                with st.spinner("이미지 생성 중..."):
                    image_url = generate_image(prompt)
                    if image_url:
                        st.image(image_url, caption="생성된 이미지")
                        full_response = "요청하신 이미지를 생성했습니다. 위의 이미지를 확인해 주세요."
                        chatbot['messages'].append({"role": "assistant", "content": full_response, "image_url": image_url})
                    else:
                        full_response = "죄송합니다. 이미지 생성 중 오류가 발생했습니다. 다른 주제로 시도해 보시거나, 요청을 더 구체적으로 해주세요."
            else:
                try:
                    if "gpt" in selected_model:
                        response = openai_client.chat.completions.create(
                            model=selected_model,
                            messages=[{"role": "system", "content": SYSTEM_MESSAGE}] + chatbot['messages'],
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
                            messages=chatbot['messages'],
                            model=selected_model,
                            system=SYSTEM_MESSAGE,
                        ) as stream:
                            for text in stream.text_stream:
                                full_response += text
                                message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")
            
            if full_response:
                chatbot['messages'].append({"role": "assistant", "content": full_response})
                
        # 데이터베이스 업데이트
        if db is not None:  # 여기를 수정했습니다
            try:
                db.users.update_one(
                    {"_id": st.session_state.user["_id"]},
                    {"$set": {f"chatbots.{st.session_state.current_chatbot}": chatbot}}
                )
            except Exception as e:
                st.error(f"대화 내용 저장 중 오류가 발생했습니다: {str(e)}")
        else:
            st.session_state.user["chatbots"][st.session_state.current_chatbot] = chatbot

    if st.button("대화 내역 초기화"):
        chatbot['messages'] = []
        if db is not None:  # 여기도 수정했습니다
            try:
                db.users.update_one(
                    {"_id": st.session_state.user["_id"]},
                    {"$set": {f"chatbots.{st.session_state.current_chatbot}.messages": []}}
                )
            except Exception as e:
                st.error(f"대화 내역 초기화 중 오류가 발생했습니다: {str(e)}")
        st.rerun()

# 메인 애플리케이션
def main_app():
    # 사이드바 메뉴
    st.sidebar.title("메뉴")
    if st.sidebar.button("홈"):
        st.session_state.current_page = 'home'
        st.rerun()
    if st.sidebar.button("새 챗봇 만들기"):
        st.session_state.current_page = 'create_chatbot'
        st.rerun()
    if st.sidebar.button("사용 가능한 챗봇"):
        st.session_state.current_page = 'available_chatbots'
        st.rerun()
    if st.sidebar.button("로그아웃"):
        st.session_state.user = None
        st.session_state.current_page = 'home'
        st.rerun()

    # 현재 페이지에 따라 적절한 내용 표시
    if st.session_state.current_page == 'home':
        show_home_page()
    elif st.session_state.current_page == 'create_chatbot':
        show_create_chatbot_page()
    elif st.session_state.current_page == 'available_chatbots':
        show_available_chatbots_page()
    elif st.session_state.current_page == 'chatbot':
        show_chatbot_page()

# 메인 실행 부분
if 'user' not in st.session_state or not st.session_state.user:
    show_login_page()
else:
    main_app()
