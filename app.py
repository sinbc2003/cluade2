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

# CSS 스타일 추가
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        border-radius: 20px;
        height: 3em;
        background-color: #E6F3FF;
        color: #000000;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .stButton > button:hover {
        background-color: #B3D9FF;
    }
    .chatbot-card {
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        height: 100%;
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .chatbot-profile {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        object-fit: cover;
    }
    .chatbot-info {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }
    .chatbot-description {
        flex-grow: 1;
        color: #333;
    }
    .chatbot-name {
        color: #000;
        font-weight: bold;
    }
    .small-button {
        font-size: 0.8em;
        padding: 0.2em 0.5em;
    }
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 500px;
        border: 1px solid #ccc;
        padding: 10px;
    }
    .chat-messages {
        flex: 1;
        overflow-y: auto;
        margin-bottom: 10px;
    }
    .chat-input {
        position: sticky;
        bottom: 0;
        background: white;
        padding-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# MongoDB 연결
try:
    MONGO_URI = st.secrets["MONGO_URI"]
    client = MongoClient(MONGO_URI)
    db = client.get_database("chatbot_platform")
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
                st.experimental_rerun()
            else:
                st.error("아이디 또는 비밀번호가 잘못되었습니다.")

# 홈 페이지 (기본 챗봇)
def show_home_page():
    st.title("기본 챗봇")
    selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)

    if 'home_messages' not in st.session_state:
        st.session_state.home_messages = []

    # 채팅창 컨테이너
    chat_container = st.container()
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        chat_messages = st.container()
        with chat_messages:
            for message in st.session_state.home_messages:
                with st.chat_message(message["role"]):
                    if message["role"] == "assistant" and "image_url" in message:
                        st.image(message["image_url"], caption="생성된 이미지")
                    st.markdown(message["content"])
        st.markdown('</div>', unsafe_allow_html=True)

    # 채팅 입력창 고정
    st.markdown('<div class="chat-input">', unsafe_allow_html=True)
    prompt = st.text_input("메시지를 입력하세요", key="home_prompt")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("초기화", key="reset_home"):
        st.session_state.home_messages = []
        st.experimental_rerun()

    if prompt:
        st.session_state.home_messages.append({"role": "user", "content": prompt})
        with chat_messages:
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
                                messages=[{"role": "system", "content": "당신은 도움이 되는 AI 어시스턴트입니다."}] + st.session_state.home_messages,
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
                                system="당신은 도움이 되는 AI 어시스턴트입니다.",
                            ) as stream:
                                for text in stream.text_stream:
                                    full_response += text
                                    message_placeholder.markdown(full_response + "▌")

                        message_placeholder.markdown(full_response)
                    except Exception as e:
                        st.error("응답 생성 중 오류가 발생했습니다. 다시 시도해주세요.")

                    if full_response:
                        st.session_state.home_messages.append({"role": "assistant", "content": full_response})

        st.experimental_rerun()

# 새 챗봇 만들기 페이지
def show_create_chatbot_page():
    st.title("새 챗봇 만들기")
    col_left, col_right = st.columns(2)

    with col_left:
        chatbot_name = st.text_input("챗봇 이름")
        chatbot_description = st.text_input("챗봇 소개")
        system_prompt = st.text_area("시스템 프롬프트", value="당신은 도움이 되는 AI 어시스턴트입니다.", height=200)
        welcome_message = st.text_input("웰컴 메시지", value="안녕하세요! 무엇을 도와드릴까요?")
        background_color = st.color_picker("챗봇 카드 배경색", value="#F0F8FF")
        is_shared = st.checkbox("다른 교사와 공유하기")

        if st.button("프로필 이미지 생성"):
            profile_image_prompt = f"Create a profile image for a chatbot named '{chatbot_name}'. Description: {chatbot_description}"
            profile_image_url = generate_image(profile_image_prompt)
            if profile_image_url:
                st.image(profile_image_url, caption="생성된 프로필 이미지", width=200)
                st.session_state.new_chatbot_profile_image_url = profile_image_url
            else:
                st.error("프로필 이미지 생성에 실패했습니다.")

        if st.button("챗봇 생성"):
            new_chatbot = {
                "name": chatbot_name,
                "description": chatbot_description,
                "system_prompt": system_prompt,
                "welcome_message": welcome_message,
                "messages": [{"role": "assistant", "content": welcome_message}],
                "creator": st.session_state.user["username"],
                "is_shared": is_shared,
                "background_color": background_color,
                "profile_image_url": st.session_state.get('new_chatbot_profile_image_url', 'https://via.placeholder.com/100')
            }
            if db is not None:
                try:
                    if is_shared:
                        db.shared_chatbots.insert_one(new_chatbot)
                    else:
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

    with col_right:
        st.header("챗봇 테스트")
        if 'test_chatbot_messages' not in st.session_state:
            st.session_state.test_chatbot_messages = [{"role": "assistant", "content": welcome_message}]
        else:
            st.session_state.test_chatbot_messages[0] = {"role": "assistant", "content": welcome_message}

        # 채팅창 컨테이너
        chat_container = st.container()
        with chat_container:
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            chat_messages = st.container()
            with chat_messages:
                for message in st.session_state.test_chatbot_messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
            st.markdown('</div>', unsafe_allow_html=True)

        # 채팅 입력창 고정
        st.markdown('<div class="chat-input">', unsafe_allow_html=True)
        test_prompt = st.text_input("메시지를 입력하세요", key="test_prompt")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("초기화", key="reset_test_chatbot"):
            st.session_state.test_chatbot_messages = [{"role": "assistant", "content": welcome_message}]
            st.experimental_rerun()

        if test_prompt:
            st.session_state.test_chatbot_messages.append({"role": "user", "content": test_prompt})
            with chat_messages:
                with st.chat_message("user"):
                    st.markdown(test_prompt)

                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = ""
                    try:
                        response = openai_client.chat.completions.create(
                            model="gpt-4",
                            messages=[{"role": "system", "content": system_prompt}] + st.session_state.test_chatbot_messages,
                            stream=True
                        )
                        for chunk in response:
                            if chunk.choices[0].delta.content is not None:
                                full_response += chunk.choices[0].delta.content
                                message_placeholder.markdown(full_response + "▌")
                        message_placeholder.markdown(full_response)
                    except Exception as e:
                        st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")

                    if full_response:
                        st.session_state.test_chatbot_messages.append({"role": "assistant", "content": full_response})

            st.experimental_rerun()

# 사용 가능한 챗봇 페이지
def show_available_chatbots_page():
    st.title("사용 가능한 챗봇")
    cols = st.columns(2)  # 2열로 변경
    for i, chatbot in enumerate(st.session_state.user["chatbots"]):
        with cols[i % 2]:  # 2열로 변경
            st.markdown(f"""
            <div class="chatbot-card" style="background-color: {chatbot.get('background_color', '#F0F8FF')};">
                <div style="display: flex;">
                    <div style="flex: 0 0 100px;">
                        <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/100')}" class="chatbot-profile">
                    </div>
                    <div class="chatbot-info" style="flex: 1; padding-left: 20px;">
                        <h3 class="chatbot-name">{chatbot['name']}</h3>
                        <div class="chatbot-description">{chatbot['description']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"사용하기 #{i}", key=f"use_{i}"):
                    st.session_state.current_chatbot = i
                    st.session_state.current_page = 'chatbot'
                    st.experimental_rerun()
            with col2:
                if chatbot.get('creator') == st.session_state.user["username"]:
                    if st.button(f"지침 수정 #{i}", key=f"edit_{i}"):
                        st.session_state.edit_chatbot = i
                        st.session_state.current_page = 'edit_chatbot'
                        st.experimental_rerun()

# 특정 챗봇 페이지
def show_chatbot_page():
    chatbot = st.session_state.user["chatbots"][st.session_state.current_chatbot]
    st.title(f"{chatbot['name']} 챗봇")
    selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)

    if 'chatbot_messages' not in st.session_state:
        st.session_state.chatbot_messages = chatbot['messages']

    # 채팅창 컨테이너
    chat_container = st.container()
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        chat_messages = st.container()
        with chat_messages:
            for message in st.session_state.chatbot_messages:
                with st.chat_message(message["role"]):
                    if message["role"] == "assistant" and "image_url" in message:
                        st.image(message["image_url"], caption="생성된 이미지")
                    st.markdown(message["content"])
        st.markdown('</div>', unsafe_allow_html=True)

    # 채팅 입력창 고정
    st.markdown('<div class="chat-input">', unsafe_allow_html=True)
    prompt = st.text_input("메시지를 입력하세요", key="chatbot_prompt")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("초기화", key="reset_chatbot"):
        st.session_state.chatbot_messages = [{"role": "assistant", "content": chatbot['welcome_message']}]
        if db is not None:
            try:
                db.users.update_one(
                    {"_id": st.session_state.user["_id"]},
                    {"$set": {f"chatbots.{st.session_state.current_chatbot}.messages": st.session_state.chatbot_messages}}
                )
            except Exception as e:
                st.error(f"대화 내역 초기화 중 오류가 발생했습니다: {str(e)}")
        st.experimental_rerun()

    if prompt:
        st.session_state.chatbot_messages.append({"role": "user", "content": prompt})
        with chat_messages:
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
                            st.session_state.chatbot_messages.append({"role": "assistant", "content": full_response, "image_url": image_url})
                        else:
                            full_response = "죄송합니다. 이미지 생성 중 오류가 발생했습니다. 다른 주제로 시도해 보시거나, 요청을 더 구체적으로 해주세요."
                else:
                    try:
                        if "gpt" in selected_model:
                            response = openai_client.chat.completions.create(
                                model=selected_model,
                                messages=[{"role": "system", "content": chatbot['system_prompt']}] + st.session_state.chatbot_messages,
                                stream=True
                            )
                            for chunk in response:
                                if chunk.choices[0].delta.content is not None:
                                    full_response += chunk.choices[0].delta.content
                                    message_placeholder.markdown(full_response + "▌")
                        elif "gemini" in selected_model:
                            model = genai.GenerativeModel(selected_model)
                            response = model.generate_content(chatbot['system_prompt'] + "\n\n" + prompt, stream=True)
                            for chunk in response:
                                if chunk.text:
                                    full_response += chunk.text
                                    message_placeholder.markdown(full_response + "▌")
                        elif "claude" in selected_model:
                            with anthropic_client.messages.stream(
                                max_tokens=1000,
                                messages=st.session_state.chatbot_messages,
                                model=selected_model,
                                system=chatbot['system_prompt'],
                            ) as stream:
                                for text in stream.text_stream:
                                    full_response += text
                                    message_placeholder.markdown(full_response + "▌")

                        message_placeholder.markdown(full_response)
                    except Exception as e:
                        st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")

                    if full_response:
                        st.session_state.chatbot_messages.append({"role": "assistant", "content": full_response})

        # 데이터베이스 업데이트
        if db is not None:
            try:
                db.users.update_one(
                    {"_id": st.session_state.user["_id"]},
                    {"$set": {f"chatbots.{st.session_state.current_chatbot}.messages": st.session_state.chatbot_messages}}
                )
            except Exception as e:
                st.error(f"대화 내용 저장 중 오류가 발생했습니다: {str(e)}")
        else:
            st.session_state.user["chatbots"][st.session_state.current_chatbot]['messages'] = st.session_state.chatbot_messages

        st.experimental_rerun()

# 메인 애플리케이션
def main_app():
    # 사이드바 메뉴
    st.sidebar.title("메뉴")
    if st.sidebar.button("홈"):
        st.session_state.current_page = 'home'
        st.experimental_rerun()
    if st.sidebar.button("새 챗봇 만들기"):
        st.session_state.current_page = 'create_chatbot'
        st.experimental_rerun()
    if st.sidebar.button("사용 가능한 챗봇"):
        st.session_state.current_page = 'available_chatbots'
        st.experimental_rerun()
    if st.sidebar.button("로그아웃"):
        st.session_state.user = None
        st.session_state.current_page = 'home'
        st.experimental_rerun()

    # 현재 페이지에 따라 적절한 내용 표시
    if st.session_state.current_page == 'home':
        show_home_page()
    elif st.session_state.current_page == 'create_chatbot':
        show_create_chatbot_page()
    elif st.session_state.current_page == 'available_chatbots':
        show_available_chatbots_page()
    elif st.session_state.current_page == 'chatbot':
        show_chatbot_page()
    elif st.session_state.current_page == 'edit_chatbot':
        show_edit_chatbot_page()

# 메인 실행 부분
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'home'

if 'user' not in st.session_state or not st.session_state.user:
    show_login_page()
else:
    main_app()
