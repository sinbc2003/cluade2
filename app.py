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
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import gspread
from google.auth.exceptions import GoogleAuthError
import traceback

# 전역 변수로 db 선언
db = None

# Streamlit 페이지 설정
st.set_page_config(page_title="Chatbot Platform", page_icon=":robot_face:", layout="wide")

# CSS 스타일 추가
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #f0f8ff;
        color: #4682b4;
        border: 1px solid #4682b4;
        border-radius: 5px;
        padding: 8px 16px;
        font-size: 12.8px;  /* 기존 16px의 80% */
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #4682b4;
        color: #f0f8ff;
    }
    .chatbot-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
        display: flex;
        align-items: start;
        height: 160px;
        overflow: hidden;
    }
    .chatbot-card img {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 20px;
    }
    .chatbot-info {
        flex-grow: 1;
        overflow: hidden;
    }
    .chatbot-name {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .chatbot-description {
        font-size: 14px;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }
    .chatbot-title {
        display: flex;
        align-items: center;
        margin-bottom: 20px;
    }
    .chatbot-title img {
        width: 80px;  /* 프로필 사진을 더 크게 */
        height: 80px;
        border-radius: 50%;
        margin-right: 15px;
    }
    .edit-button {
        font-size: 1.6px;  /* 현재 크기의 10%로 줄임 */
        padding: 5px 10px;
        margin-left: 10px;
    }
    .reset-button {
        background-color: #98FB98;
        color: #000000;
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

# Google Sheets API 설정
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    service_account_info = dict(st.secrets["gcp_service_account"])

    # private_key의 줄 바꿈 처리
    if 'private_key' in service_account_info:
        private_key = service_account_info['private_key']
        if '\\n' in private_key:
            private_key = private_key.replace('\\n', '\n')
            service_account_info['private_key'] = private_key

    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    gs_client = gspread.authorize(creds)

    # 스프레드시트 열기
    sheet_url = "https://docs.google.com/spreadsheets/d/1ql6GXd3KYPywP3wNeXrgJTfWf8aCP8fGXUvGYbmlmic/edit?gid=0"
    try:
        sheet = gs_client.open_by_url(sheet_url).sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"스프레드시트를 찾을 수 없습니다. URL을 확인해주세요: {sheet_url}")
        sheet = None
    except gspread.exceptions.NoValidUrlKeyFound:
        st.error(f"올바르지 않은 스프레드시트 URL입니다: {sheet_url}")
        sheet = None
    except gspread.exceptions.APIError as e:
        if 'PERMISSION_DENIED' in str(e):
            st.error("스프레드시트에 접근할 권한이 없습니다. 서비스 계정 이메일을 스프레드시트의 공유 설정에 추가했는지 확인해주세요.")
        else:
            st.error(f"Google Sheets API 오류: {str(e)}")
        sheet = None
except GoogleAuthError as e:
    st.error(f"Google 인증 오류: {str(e)}")
    sheet = None
except Exception as e:
    st.error(f"Google Sheets 설정 중 오류가 발생했습니다: {str(e)}")
    st.error(traceback.format_exc())  # 예외의 상세 정보 출력
    sheet = None

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

# 로그인 함수 수정
def login(username, password):
    if sheet is None:
        st.error("Google Sheets 연결에 실패하여 로그인할 수 없습니다.")
        return None

    try:
        # 사용자 찾기
        records = sheet.get_all_records()
        for record in records:
            if record['아이디'] == username and str(record['비밀번호']) == password:
                if password == "1111":
                    return "change_password"
                return {"username": username, "chatbots": []}
    except Exception as e:
        st.error(f"로그인 중 오류가 발생했습니다: {str(e)}")
    return None

# 비밀번호 변경 함수 수정
def change_password(username, new_password):
    if sheet is None:
        st.error("Google Sheets 연결에 실패하여 비밀번호를 변경할 수 없습니다.")
        return False

    try:
        # 모든 데이터 가져오기
        records = sheet.get_all_records()
        for idx, record in enumerate(records, start=2):  # 헤더를 제외하고 2부터 시작
            if record['아이디'] == username:
                # 비밀번호 업데이트
                sheet.update_cell(idx, 2, new_password)
                return True
        return False
    except Exception as e:
        st.error(f"비밀번호 변경 중 오류가 발생했습니다: {str(e)}")
        return False

# 세션 상태 초기화
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'
if 'user' not in st.session_state:
    st.session_state.user = None

# 로그인 페이지
def show_login_page():
    st.title("로그인")
    username = st.text_input("아이디", key="login_username")
    password = st.text_input("비밀번호", type="password", key="login_password")
    if st.button("로그인", on_click=login_action):
        pass

def login_action():
    with st.spinner("로그인 중..."):
        username = st.session_state.login_username
        password = st.session_state.login_password
        result = login(username, password)
        if result == "change_password":
            st.session_state.current_page = 'change_password'
            st.session_state.username = username
            st.warning("초기 비밀번호를 사용 중입니다. 비밀번호를 변경해주세요.")
        elif result:
            st.session_state.user = result
            st.session_state.current_page = 'home'
            st.success("로그인 성공!")
        else:
            st.error("아이디 또는 비밀번호가 잘못되었습니다.")

# 비밀번호 변경 페이지
def show_change_password_page():
    st.title("비밀번호 변경")
    new_password = st.text_input("새 비밀번호", type="password", key="new_password")
    confirm_password = st.text_input("새 비밀번호 확인", type="password", key="confirm_password")
    if st.button("비밀번호 변경", on_click=change_password_action):
        pass

def change_password_action():
    new_password = st.session_state.new_password
    confirm_password = st.session_state.confirm_password
    if new_password == confirm_password:
        if change_password(st.session_state.username, new_password):
            st.success("비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 다시 로그인해주세요.")
            st.session_state.current_page = 'login'
            st.session_state.username = ''
        else:
            st.error("비밀번호 변경에 실패했습니다.")
    else:
        st.error("새 비밀번호가 일치하지 않습니다.")

# 대화 내역 저장 함수
def save_chat_history(chatbot_name, messages):
    if db is not None:
        try:
            chat_history = {
                "chatbot_name": chatbot_name,
                "user": st.session_state.user["username"],
                "timestamp": datetime.now(),
                "messages": messages
            }
            db.chat_history.insert_one(chat_history)
        except Exception as e:
            st.error(f"대화 내역 저장 중 오류가 발생했습니다: {str(e)}")

# 오래된 대화 내역 삭제 함수
def delete_old_chat_history():
    if db is not None:
        try:
            one_month_ago = datetime.now() - timedelta(days=30)
            db.chat_history.delete_many({"timestamp": {"$lt": one_month_ago}})
        except Exception as e:
            st.error(f"오래된 대화 내역 삭제 중 오류가 발생했습니다: {str(e)}")

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

    if st.sidebar.button("현재 대화내역 초기화", key="reset_chat", help="현재 대화 내역을 초기화합니다.", use_container_width=True):
        st.session_state.home_messages = []

# 새 챗봇 만들기 페이지
def show_create_chatbot_page():
    st.title("새 챗봇 만들기")
    chatbot_name = st.text_input("챗봇 이름")
    chatbot_description = st.text_input("챗봇 소개")
    system_prompt = st.text_area("시스템 프롬프트", value="당신은 도움이 되는 AI 어시스턴트입니다.", height=300)
    welcome_message = st.text_input("웰컴 메시지", value="안녕하세요! 무엇을 도와드릴까요?")
    is_shared = st.checkbox("다른 교사와 공유하기")
    background_color = st.color_picker("챗봇 카드 배경색 선택", "#FFFFFF")

    if 'temp_profile_image_url' not in st.session_state:
        st.session_state.temp_profile_image_url = "https://via.placeholder.com/100"

    st.image(st.session_state.temp_profile_image_url, caption="프로필 이미지", width=200)

    if st.button("프로필 이미지 생성"):
        with st.spinner("프로필 이미지를 생성 중입니다. 잠시만 기다려주세요..."):
            profile_image_prompt = f"Create a profile image for a chatbot named '{chatbot_name}'. Description: {chatbot_description}"
            generated_image_url = generate_image(profile_image_prompt)
            if generated_image_url:
                st.session_state.temp_profile_image_url = generated_image_url
                st.image(generated_image_url, caption="생성된 프로필 이미지", width=200)
                st.success("프로필 이미지가 생성되었습니다.")
            else:
                st.error("프로필 이미지 생성에 실패했습니다. 기본 이미지가 사용됩니다.")

    if st.button("챗봇 생성", on_click=create_chatbot_action):
        pass

def create_chatbot_action():
    chatbot_name = st.session_state['챗봇 이름']
    chatbot_description = st.session_state['챗봇 소개']
    system_prompt = st.session_state['시스템 프롬프트']
    welcome_message = st.session_state['웰컴 메시지']
    is_shared = st.session_state['다른 교사와 공유하기']
    background_color = st.session_state['챗봇 카드 배경색 선택']
    profile_image_url = st.session_state.get('temp_profile_image_url', "https://via.placeholder.com/100")

    new_chatbot = {
        "name": chatbot_name,
        "description": chatbot_description,
        "system_prompt": system_prompt,
        "welcome_message": welcome_message,
        "messages": [{"role": "assistant", "content": welcome_message}],
        "creator": st.session_state.user["username"],
        "is_shared": is_shared,
        "background_color": background_color,
        "profile_image_url": profile_image_url
    }
    if db is not None:
        try:
            if is_shared:
                result = db.shared_chatbots.insert_one(new_chatbot)
                new_chatbot['_id'] = result.inserted_id
            else:
                db.users.update_one(
                    {"username": st.session_state.user["username"]},
                    {"$push": {"chatbots": new_chatbot}},
                    upsert=True
                )
                st.session_state.user = db.users.find_one({"username": st.session_state.user["username"]})
            st.success(f"'{chatbot_name}' 챗봇이 생성되었습니다!")
            # 임시 프로필 이미지 URL 유지
            # 새로 생성된 챗봇으로 이동
            if is_shared:
                st.session_state.current_shared_chatbot = new_chatbot
                st.session_state.current_page = 'shared_chatbot'
            else:
                st.session_state.current_chatbot = len(st.session_state.user['chatbots']) - 1
                st.session_state.current_page = 'chatbot'
        except Exception as e:
            st.error(f"챗봇 생성 중 오류가 발생했습니다: {str(e)}")
    else:
        if 'chatbots' not in st.session_state.user:
            st.session_state.user['chatbots'] = []
        st.session_state.user['chatbots'].append(new_chatbot)
        st.success(f"'{chatbot_name}' 챗봇이 생성되었습니다! (오프라인 모드)")
        # 임시 프로필 이미지 URL 유지
        # 새로 생성된 챗봇으로 이동
        st.session_state.current_chatbot = len(st.session_state.user['chatbots']) - 1
        st.session_state.current_page = 'chatbot'

# 챗봇 수정 페이지
def show_edit_chatbot_page():
    st.title("챗봇 수정")

    if 'editing_chatbot' not in st.session_state:
        st.error("수정할 챗봇이 선택되지 않았습니다.")
        return

    chatbot = st.session_state.user["chatbots"][st.session_state.editing_chatbot]

    new_name = st.text_input("챗봇 이름", value=chatbot['name'], key='edit_name')
    new_description = st.text_input("챗봇 소개", value=chatbot['description'], key='edit_description')
    new_system_prompt = st.text_area("시스템 프롬프트", value=chatbot['system_prompt'], height=200, key='edit_system_prompt')
    new_welcome_message = st.text_input("웰컴 메시지", value=chatbot['welcome_message'], key='edit_welcome_message')
    new_background_color = st.color_picker("챗봇 카드 배경색 선택", value=chatbot.get('background_color', '#FFFFFF'), key='edit_background_color')

    st.image(chatbot.get('profile_image_url', 'https://via.placeholder.com/100'), caption="현재 프로필 이미지", width=200)

    if st.button("프로필 이미지 재생성"):
        with st.spinner("프로필 이미지를 재생성 중입니다. 잠시만 기다려주세요..."):
            profile_image_prompt = f"Create a profile image for a chatbot named '{new_name}'. Description: {new_description}"
            new_profile_image_url = generate_image(profile_image_prompt)
            if new_profile_image_url:
                st.image(new_profile_image_url, caption="새로 생성된 프로필 이미지", width=200)
                chatbot['profile_image_url'] = new_profile_image_url
                st.success("프로필 이미지가 재생성되었습니다.")
            else:
                st.error("프로필 이미지 재생성에 실패했습니다. 기존 이미지가 유지됩니다.")

    if st.button("변경 사항 저장", on_click=save_edited_chatbot):
        pass

def save_edited_chatbot():
    chatbot = st.session_state.user["chatbots"][st.session_state.editing_chatbot]

    chatbot['name'] = st.session_state.edit_name
    chatbot['description'] = st.session_state.edit_description
    chatbot['system_prompt'] = st.session_state.edit_system_prompt
    chatbot['welcome_message'] = st.session_state.edit_welcome_message
    chatbot['background_color'] = st.session_state.edit_background_color

    if db is not None:
        try:
            db.users.update_one(
                {"username": st.session_state.user["username"]},
                {"$set": {f"chatbots.{st.session_state.editing_chatbot}": chatbot}}
            )
            st.success("챗봇이 성공적으로 수정되었습니다.")
            st.session_state.pop('editing_chatbot', None)
            st.session_state.current_page = 'chatbot'
            st.session_state.current_chatbot = st.session_state.editing_chatbot
        except Exception as e:
            st.error(f"챗봇 수정 중 오류가 발생했습니다: {str(e)}")
    else:
        st.session_state.user['chatbots'][st.session_state.editing_chatbot] = chatbot
        st.success("챗봇이 성공적으로 수정되었습니다. (오프라인 모드)")
        st.session_state.pop('editing_chatbot', None)
        st.session_state.current_page = 'chatbot'
        st.session_state.current_chatbot = st.session_state.editing_chatbot

# 사용 가능한 챗봇 페이지
def show_available_chatbots_page():
    st.title("사용 가능한 챗봇")

    if not st.session_state.user.get("chatbots"):
        st.info("아직 만든 챗봇이 없습니다. '새 챗봇 만들기'에서 첫 번째 챗봇을 만들어보세요!")
        return

    cols = st.columns(3)
    for i, chatbot in enumerate(st.session_state.user["chatbots"]):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="chatbot-card" style="background-color: {chatbot.get('background_color', '#FFFFFF')}">
                <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/100')}" alt="프로필 이미지">
                <div class="chatbot-info">
                    <div class="chatbot-name">{chatbot['name']}</div>
                    <div class="chatbot-description">{chatbot['description']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("사용하기", key=f"use_{i}", on_click=lambda idx=i: use_chatbot(idx)):
                    pass
            with col2:
                if st.button("수정하기", key=f"edit_{i}", on_click=lambda idx=i: edit_chatbot(idx)):
                    pass
            with col3:
                if st.button("삭제하기", key=f"delete_{i}", on_click=lambda idx=i: delete_chatbot_action(idx)):
                    pass

def use_chatbot(idx):
    st.session_state.current_chatbot = idx
    st.session_state.current_page = 'chatbot'

def edit_chatbot(idx):
    st.session_state.editing_chatbot = idx
    st.session_state.current_page = 'edit_chatbot'

def delete_chatbot_action(idx):
    if delete_chatbot(idx):
        st.success(f"'{st.session_state.user['chatbots'][idx]['name']}' 챗봇이 삭제되었습니다.")
        st.experimental_rerun()

    # 챗봇 삭제 함수
    def delete_chatbot(index):
        if db is not None:
            try:
                chatbot = st.session_state.user["chatbots"][index]
                db.users.update_one(
                    {"username": st.session_state.user["username"]},
                    {"$pull": {"chatbots": {"name": chatbot["name"]}}}
                )
                # 관련된 대화 내역도 삭제
                db.chat_history.delete_many({"chatbot_name": chatbot["name"], "user": st.session_state.user["username"]})
                # 사용자 정보 업데이트
                st.session_state.user = db.users.find_one({"username": st.session_state.user["username"]})
                return True
            except Exception as e:
                st.error(f"챗봇 삭제 중 오류가 발생했습니다: {str(e)}")
                return False
        else:
            st.session_state.user["chatbots"].pop(index)
            return True

    # 공유 챗봇 페이지
    def show_shared_chatbots_page():
        st.title("수원외국어고등학교 공유 챗봇")
        if db is not None:
            shared_chatbots = list(db.shared_chatbots.find())
            cols = st.columns(3)
            for i, chatbot in enumerate(shared_chatbots):
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="chatbot-card" style="background-color: {chatbot.get('background_color', '#FFFFFF')}">
                        <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/100')}" alt="프로필 이미지">
                        <div class="chatbot-info">
                            <div class="chatbot-name">{chatbot['name']}</div>
                            <div class="chatbot-description">{chatbot['description']}</div>
                            <p>작성자: {chatbot['creator']}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("사용하기", key=f"use_shared_{i}", on_click=lambda idx=i: use_shared_chatbot(idx)):
                            pass
                    with col2:
                        if chatbot['creator'] == st.session_state.user["username"]:
                            if st.button("수정하기", key=f"edit_shared_{i}", on_click=lambda idx=i: edit_shared_chatbot(idx)):
                                pass
                    with col3:
                        if chatbot['creator'] == st.session_state.user["username"]:
                            if st.button("삭제하기", key=f"delete_shared_{i}", on_click=lambda idx=i: delete_shared_chatbot_action(idx)):
                                pass
        else:
            st.write("데이터베이스 연결이 없어 공유 챗봇을 불러올 수 없습니다.")

    def use_shared_chatbot(idx):
        shared_chatbots = list(db.shared_chatbots.find())
        st.session_state.current_shared_chatbot = shared_chatbots[idx]
        st.session_state.current_page = 'shared_chatbot'

    def edit_shared_chatbot(idx):
        shared_chatbots = list(db.shared_chatbots.find())
        st.session_state.editing_shared_chatbot = shared_chatbots[idx]
        st.session_state.current_page = 'edit_shared_chatbot'

    def delete_shared_chatbot_action(idx):
        shared_chatbots = list(db.shared_chatbots.find())
        chatbot_id = shared_chatbots[idx]['_id']
        if delete_shared_chatbot(chatbot_id):
            st.success(f"'{shared_chatbots[idx]['name']}' 공유 챗봇이 삭제되었습니다.")
            st.experimental_rerun()

    # 공유 챗봇 삭제 함수
    def delete_shared_chatbot(chatbot_id):
        if db is not None:
            try:
                result = db.shared_chatbots.delete_one({"_id": chatbot_id, "creator": st.session_state.user["username"]})
                if result.deleted_count > 0:
                    return True
                else:
                    st.error("삭제 권한이 없거나 챗봇을 찾을 수 없습니다.")
                    return False
            except Exception as e:
                st.error(f"공유 챗봇 삭제 중 오류가 발생했습니다: {str(e)}")
                return False
        else:
            st.error("데이터베이스 연결이 없어 공유 챗봇을 삭제할 수 없습니다.")
            return False

    # 공유 챗봇 수정 페이지
    def show_edit_shared_chatbot_page():
        st.title("공유 챗봇 수정")

        if 'editing_shared_chatbot' not in st.session_state:
            st.error("수정할 공유 챗봇이 선택되지 않았습니다.")
            return

        chatbot = st.session_state.editing_shared_chatbot

        new_name = st.text_input("챗봇 이름", value=chatbot['name'], key='edit_shared_name')
        new_description = st.text_input("챗봇 소개", value=chatbot['description'], key='edit_shared_description')
        new_system_prompt = st.text_area("시스템 프롬프트", value=chatbot['system_prompt'], height=200, key='edit_shared_system_prompt')
        new_welcome_message = st.text_input("웰컴 메시지", value=chatbot['welcome_message'], key='edit_shared_welcome_message')
        new_background_color = st.color_picker("챗봇 카드 배경색 선택", value=chatbot.get('background_color', '#FFFFFF'), key='edit_shared_background_color')

        st.image(chatbot.get('profile_image_url', 'https://via.placeholder.com/100'), caption="현재 프로필 이미지", width=200)

        if st.button("프로필 이미지 재생성"):
            with st.spinner("프로필 이미지를 재생성 중입니다. 잠시만 기다려주세요..."):
                profile_image_prompt = f"Create a profile image for a chatbot named '{new_name}'. Description: {new_description}"
                new_profile_image_url = generate_image(profile_image_prompt)
                if new_profile_image_url:
                    st.image(new_profile_image_url, caption="새로 생성된 프로필 이미지", width=200)
                    chatbot['profile_image_url'] = new_profile_image_url
                    st.success("프로필 이미지가 재생성되었습니다.")
                else:
                    st.error("프로필 이미지 재생성에 실패했습니다. 기존 이미지가 유지됩니다.")

        if st.button("변경 사항 저장", on_click=save_edited_shared_chatbot):
            pass

    def save_edited_shared_chatbot():
        chatbot = st.session_state.editing_shared_chatbot

        chatbot['name'] = st.session_state.edit_shared_name
        chatbot['description'] = st.session_state.edit_shared_description
        chatbot['system_prompt'] = st.session_state.edit_shared_system_prompt
        chatbot['welcome_message'] = st.session_state.edit_shared_welcome_message
        chatbot['background_color'] = st.session_state.edit_shared_background_color

        if db is not None:
            try:
                db.shared_chatbots.update_one(
                    {"_id": chatbot["_id"]},
                    {"$set": chatbot}
                )
                st.success("공유 챗봇이 성공적으로 수정되었습니다.")
                st.session_state.pop('editing_shared_chatbot', None)
                st.session_state.current_page = 'shared_chatbot'
                st.session_state.current_shared_chatbot = chatbot
            except Exception as e:
                st.error(f"공유 챗봇 수정 중 오류가 발생했습니다: {str(e)}")
        else:
            st.error("데이터베이스 연결이 없어 공유 챗봇을 수정할 수 없습니다.")

    # 특정 챗봇 페이지
    def show_chatbot_page():
        chatbot = st.session_state.user["chatbots"][st.session_state.current_chatbot]

        # 제목과 프로필 이미지를 함께 표시
        st.markdown(f"""
        <div class="chatbot-title">
            <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/50')}" alt="프로필 이미지">
            <h1>{chatbot['name']} 챗봇</h1>
        </div>
        """, unsafe_allow_html=True)

        selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)

        # 사이드바에 대화 내역 초기화 버튼 추가
        if st.sidebar.button("현재 대화내역 초기화", key="reset_chat", help="현재 대화 내역을 초기화합니다.", use_container_width=True):
            # 현재 대화 내역 저장
            save_chat_history(chatbot['name'], chatbot['messages'])

            # 대화 내역 초기화
            default_welcome_message = "안녕하세요! 무엇을 도와드릴까요?"
            chatbot['messages'] = [{"role": "assistant", "content": chatbot.get('welcome_message', default_welcome_message)}]
            if db is not None:
                try:
                    db.users.update_one(
                        {"username": st.session_state.user["username"]},
                        {"$set": {f"chatbots.{st.session_state.current_chatbot}.messages": chatbot['messages']}}
                    )
                except Exception as e:
                    st.error(f"대화 내역 초기화 중 오류가 발생했습니다: {str(e)}")

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
                                messages=[{"role": "system", "content": chatbot['system_prompt']}] + chatbot['messages'],
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
                                messages=chatbot['messages'],
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
                    chatbot['messages'].append({"role": "assistant", "content": full_response})

            # 데이터베이스 업데이트
            if db is not None:
                try:
                    db.users.update_one(
                        {"username": st.session_state.user["username"]},
                        {"$set": {f"chatbots.{st.session_state.current_chatbot}": chatbot}}
                    )
                except Exception as e:
                    st.error(f"대화 내용 저장 중 오류가 발생했습니다: {str(e)}")
            else:
                st.session_state.user["chatbots"][st.session_state.current_chatbot] = chatbot

    # 공유 챗봇 대화 페이지
    def show_shared_chatbot_page():
        if 'current_shared_chatbot' not in st.session_state:
            st.error("선택된 공유 챗봇이 없습니다.")
            return

        chatbot = st.session_state.current_shared_chatbot

        # 제목과 프로필 이미지를 함께 표시
        st.markdown(f"""
        <div class="chatbot-title">
            <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/50')}" alt="프로필 이미지">
            <h1>{chatbot['name']} (공유 챗봇)</h1>
        </div>
        """, unsafe_allow_html=True)

        selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)

        # 사이드바에 대화 내역 초기화 버튼 추가
        if st.sidebar.button("현재 대화내역 초기화", key="reset_shared_chat", help="현재 대화 내역을 초기화합니다.", use_container_width=True):
            chatbot['messages'] = [{"role": "assistant", "content": chatbot.get('welcome_message', "안녕하세요! 무엇을 도와드릴까요?")}]

        if 'messages' not in chatbot:
            chatbot['messages'] = [{"role": "assistant", "content": chatbot.get('welcome_message', "안녕하세요! 무엇을 도와드릴까요?")}]

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
                                messages=[{"role": "system", "content": chatbot['system_prompt']}] + chatbot['messages'],
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
                                messages=chatbot['messages'],
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
                    chatbot['messages'].append({"role": "assistant", "content": full_response})

    # 대화 내역 확인 페이지
    def show_chat_history_page():
        st.title("대화 내역 확인")

        if 'user' in st.session_state and st.session_state.user:
            for i, chatbot in enumerate(st.session_state.user.get('chatbots', [])):
                st.subheader(f"{i+1}. {chatbot['name']}")
                st.write(chatbot['description'])
                if st.button(f"대화 내역 보기 #{i}"):
                    st.write("--- 현재 대화 내역 ---")
                    for message in chatbot['messages']:
                        st.write(f"{message['role']}: {message['content']}")
                    st.write("---")

                    if db is not None:
                        st.write("--- 이전 대화 내역 ---")
                        chat_histories = db.chat_history.find({
                            "chatbot_name": chatbot['name'],
                            "user": st.session_state.user["username"]
                        }).sort("timestamp", -1)

                        for history in chat_histories:
                            st.write(f"대화 시간: {history['timestamp']}")
                            for message in history['messages']:
                                st.write(f"{message['role']}: {message['content']}")
                            st.write("---")

                            if st.button(f"이 대화 내역 삭제 {history['_id']}"):
                                delete_specific_chat_history(history['_id'])
                                st.success("선택한 대화 내역이 삭제되었습니다.")
                    else:
                        st.warning("데이터베이스 연결이 없어 이전 대화 내역을 불러올 수 없습니다.")
        else:
            st.warning("로그인이 필요합니다.")

    # 특정 대화 내역 삭제 함수
    def delete_specific_chat_history(history_id):
        if db is not None:
            try:
                db.chat_history.delete_one({"_id": history_id})
            except Exception as e:
                st.error(f"대화 내역 삭제 중 오류가 발생했습니다: {str(e)}")

    # 메인 애플리케이션
    def main_app():
        # 사이드바 메뉴
        st.sidebar.title("메뉴")
        menu_items = [
            ("홈", 'home'),
            ("새 챗봇 만들기", 'create_chatbot'),
            ("사용 가능한 챗봇", 'available_chatbots'),
            ("수원외국어고등학교 공유 챗봇", 'shared_chatbots'),
            ("대화 내역 확인", 'chat_history'),
            ("로그아웃", 'logout')
        ]

        for label, page in menu_items:
            if st.sidebar.button(label, key=f"menu_{page}", use_container_width=True):
                if page == 'logout':
                    st.session_state.user = None
                    st.session_state.current_page = 'login'
                else:
                    st.session_state.current_page = page

        # 현재 페이지에 따라 적절한 내용 표시
        if st.session_state.current_page == 'home':
            show_home_page()
        elif st.session_state.current_page == 'create_chatbot':
            show_create_chatbot_page()
        elif st.session_state.current_page == 'available_chatbots':
            show_available_chatbots_page()
        elif st.session_state.current_page == 'shared_chatbots':
            show_shared_chatbots_page()
        elif st.session_state.current_page == 'chatbot':
            if 'current_chatbot' in st.session_state and st.session_state.current_chatbot < len(st.session_state.user.get("chatbots", [])):
                show_chatbot_page()
            else:
                st.error("선택된 챗봇을 찾을 수 없습니다.")
                st.session_state.current_page = 'available_chatbots'
        elif st.session_state.current_page == 'shared_chatbot':
            show_shared_chatbot_page()
        elif st.session_state.current_page == 'chat_history':
            show_chat_history_page()
        elif st.session_state.current_page == 'edit_chatbot':
            show_edit_chatbot_page()
        elif st.session_state.current_page == 'edit_shared_chatbot':
            show_edit_shared_chatbot_page()
        elif st.session_state.current_page == 'change_password':
            show_change_password_page()
        else:
            st.session_state.current_page = 'home'
            show_home_page()

        # 오래된 대화 내역 삭제 (1달 이상 된 내역)
        delete_old_chat_history()

    # 메인 실행 부분
    def main():
        if st.session_state.current_page == 'login':
            show_login_page()
        elif st.session_state.current_page == 'change_password':
            show_change_password_page()
        elif st.session_state.user:
            main_app()
        else:
            st.session_state.current_page = 'login'
            show_login_page()

    if __name__ == "__main__":
        main()
