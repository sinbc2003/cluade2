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
import pandas as pd
import base64  # For QR code image display
import json
from google.cloud import storage
import io
from langchain.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
import pinecone


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
        width: 150px; /* 이미지 크기를 크게 조정 */
        height: 150px;
        border-radius: 50%;
        margin-right: 15px;
    }
    .edit-button {
        font-size: 1.28px; /* 폰트 크기를 10%로 줄임 */
        padding: 0.8px 1.6px;
        margin-left: 10px;
    }
    .reset-button {
        background-color: #98FB98;
        color: #000000;
    }
    .small-button .stButton>button {
        font-size: 1.28px; /* 폰트 크기를 10%로 줄임 */
        padding: 0.8px 1.6px;
        width: auto;
        height: auto;
    }
    /* QR 코드 이미지 스타일 */
    .qr-code img {
        width: 150px;
        height: 150px;
        cursor: pointer;
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
PINECONE_API_KEY = st.secrets["PINECONE"]["API_KEY"]
PINECONE_ENVIRONMENT = st.secrets["PINECONE"]["ENVIRONMENT"]


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

# Google Sheets API 및 Google Cloud Storage 설정
try:
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/devstorage.read_write'  # Cloud Storage 접근 권한 추가
    ]
    service_account_info = dict(st.secrets["gcp_service_account"])

    # private_key의 줄 바꿈 처리
    if 'private_key' in service_account_info:
        private_key = service_account_info['private_key']
        if '\\n' in private_key:
            private_key = private_key.replace('\\n', '\n')
            service_account_info['private_key'] = private_key

    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    gs_client = gspread.authorize(creds)

    # Google Cloud Storage 클라이언트 설정
    try:
        storage_client = storage.Client(credentials=creds, project=service_account_info['project_id'])
    except Exception as e:
        st.error(f"Google Cloud Storage 클라이언트 초기화에 실패했습니다: {str(e)}")
        storage_client = None

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
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307"
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

# 이미지 업로드 함수 추가
def upload_image_to_gcs(image_data, filename):
    try:
        bucket_name = 'sawlteacher'  # 버킷 이름을 정확히 입력하세요
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_data, content_type='image/png')
        # blob.make_public() 호출 제거
        # 업로드한 객체의 공개 URL 생성
        public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
        return public_url
    except Exception as e:
        st.error(f"이미지를 Cloud Storage에 업로드하는 중 오류가 발생했습니다: {str(e)}")
        return None

# DALL-E를 사용한 이미지 생성 함수 수정
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
        image_url = response.data[0].url
        # 이미지 다운로드
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            image_data = image_response.content
            # 고유한 파일 이름 생성
            filename = f"images/{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
            # Google Cloud Storage에 업로드
            public_url = upload_image_to_gcs(image_data, filename)
            if public_url:
                return public_url
            else:
                return None
        else:
            st.error("이미지 다운로드에 실패했습니다.")
            return None
    except Exception as e:
        st.error(f"이미지 생성에 실패했습니다. 다시 시도해주세요. 오류: {str(e)}")
        return None

# 사용자 데이터 캐싱 함수
@st.cache_data(ttl=600)
def get_users_data():
    if sheet is None:
        st.error("Google Sheets 연결에 실패하여 사용자 데이터를 불러올 수 없습니다.")
        return None
    try:
        # 모든 데이터를 가져옵니다.
        values = sheet.get_all_values()
        if not values:
            st.error("스프레드시트에 데이터가 없습니다.")
            return None
        headers = [header.strip() for header in values[0]]
        data_rows = values[1:]
        records = []
        for row in data_rows:
            # 행의 길이를 헤더의 길이에 맞춥니다.
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            record = dict(zip(headers, row))
            records.append(record)
        return records
    except Exception as e:
        st.error(f"사용자 데이터 불러오기 중 오류가 발생했습니다: {str(e)}")
        return None

# 로그인 함수 수정
def login(username, password):
    users_data = get_users_data()
    if users_data is None:
        st.error("사용자 데이터를 불러올 수 없어 로그인할 수 없습니다.")
        return None

    try:
        if not users_data:
            st.error("사용자 데이터가 비어 있습니다.")
            return None

        # 첫 번째 행의 키(헤더)를 가져옵니다.
        first_row_keys = list(users_data[0].keys())
        # 키를 모두 소문자로 변환하여 비교합니다.
        lower_keys = [key.lower() for key in first_row_keys]

        # '아이디'와 '비밀번호' 키가 있는지 확인합니다.
        if '아이디' in lower_keys:
            id_key = first_row_keys[lower_keys.index('아이디')]
        else:
            st.error("스프레드시트에 '아이디' 열이 없습니다.")
            return None

        if '비밀번호' in lower_keys:
            password_key = first_row_keys[lower_keys.index('비밀번호')]
        else:
            st.error("스프레드시트에 '비밀번호' 열이 없습니다.")
            return None

        # 사용자 찾기
        for row in users_data:
            if row.get(id_key) == username:
                if row.get(password_key) == password:
                    if password == "1111":
                        return "change_password"
                    # 데이터베이스에서 사용자 정보 가져오기
                    if db is not None:
                        user = db.users.find_one({"username": username})
                        if user:
                            return user
                        else:
                            # 사용자 정보가 없으면 새로 생성
                            new_user = {"username": username, "chatbots": []}
                            db.users.insert_one(new_user)
                            return new_user
                    else:
                        return {"username": username, "chatbots": []}
                else:
                    st.error("비밀번호가 잘못되었습니다.")
                    return None
        else:
            st.error("아이디를 찾을 수 없습니다.")
            return None
    except Exception as e:
        st.error(f"로그인 중 오류가 발생했습니다: {str(e)}")
    return None

# 비밀번호 변경 함수 수정
def change_password(username, new_password):
    users_data = get_users_data()
    if users_data is None:
        st.error("사용자 데이터를 불러올 수 없어 비밀번호를 변경할 수 없습니다.")
        return False

    try:
        if not users_data:
            st.error("사용자 데이터가 비어 있습니다.")
            return False

        # 첫 번째 행의 키(헤더)를 가져옵니다.
        first_row_keys = list(users_data[0].keys())
        # 키를 모두 소문자로 변환하여 비교합니다.
        lower_keys = [key.lower() for key in first_row_keys]

        # '아이디'와 '비밀번호' 키가 있는지 확인합니다.
        if '아이디' in lower_keys:
            id_key = first_row_keys[lower_keys.index('아이디')]
        else:
            st.error("스프레드시트에 '아이디' 열이 없습니다.")
            return False

        if '비밀번호' in lower_keys:
            password_key = first_row_keys[lower_keys.index('비밀번호')]
        else:
            st.error("스프레드시트에 '비밀번호' 열이 없습니다.")
            return False

        # 사용자 찾기
        for idx, row in enumerate(users_data):
            if row.get(id_key) == username:
                # 비밀번호 업데이트
                row_number = idx + 2  # 헤더를 고려하여 +2
                col_number = lower_keys.index('비밀번호') + 1  # 인덱스가 0부터 시작하므로 +1
                sheet.update_cell(row_number, col_number, new_password)
                # 캐시 데이터 갱신
                get_users_data.clear()
                return True
        else:
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
    if st.button("로그인"):
        with st.spinner("로그인 중..."):
            result = login(username, password)
            if result == "change_password":
                st.session_state.current_page = 'change_password'
                st.session_state.username = username
                st.warning("초기 비밀번호를 사용 중입니다. 비밀번호를 변경해주세요.")
                st.rerun()
            elif result:
                st.session_state.user = result
                st.session_state.current_page = 'home'
                st.success("로그인 성공!")
                st.rerun()
            else:
                pass  # 오류 메시지는 로그인 함수에서 처리됨

# 비밀번호 변경 페이지
def show_change_password_page():
    st.title("비밀번호 변경")
    new_password = st.text_input("새 비밀번호", type="password", key="new_password")
    confirm_password = st.text_input("새 비밀번호 확인", type="password", key="confirm_password")
    if st.button("비밀번호 변경"):
        if new_password == confirm_password:
            if change_password(st.session_state.username, new_password):
                st.success("비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 다시 로그인해주세요.")
                st.session_state.current_page = 'login'
                st.session_state.username = ''
                st.rerun()
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
            db.public_chat_history.delete_many({"timestamp": {"$lt": one_month_ago}})
            db.usage_logs.delete_many({"timestamp": {"$lt": one_month_ago}})
        except Exception as e:
            st.error(f"오래된 대화 내역 삭제 중 오류가 발생했습니다: {str(e)}")

# 사용량 기록 함수 추가
def record_usage(username, model_name, timestamp, tokens_used=None):
    if db is not None:
        try:
            usage_entry = {
                "username": username,
                "model_name": model_name,
                "timestamp": timestamp,
                "tokens_used": tokens_used
            }
            db.usage_logs.insert_one(usage_entry)
        except Exception as e:
            st.error(f"사용량 기록 중 오류가 발생했습니다: {str(e)}")

# 홈 페이지 (기본 챗봇)
def show_home_page():
    st.title("Default 봇")
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
                        st.session_state.home_messages.append({"role": "assistant", "content": full_response})
            else:
                try:
                    start_time = datetime.now()
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
                        # 사용량 기록
                        record_usage(st.session_state.user["username"], selected_model, start_time)
                    elif "gemini" in selected_model:
                        model = genai.GenerativeModel(selected_model)
                        response = model.generate_content(prompt, stream=True)
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                message_placeholder.markdown(full_response + "▌")
                        record_usage(st.session_state.user["username"], selected_model, start_time)
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
                        record_usage(st.session_state.user["username"], selected_model, start_time)
                except Exception as e:
                    st.error("응답 생성 중 오류가 발생했습니다. 다시 시도해주세요.")

                if full_response:
                    st.session_state.home_messages.append({"role": "assistant", "content": full_response})

    if st.sidebar.button("현재 대화내역 초기화", key="reset_chat", help="현재 대화 내역을 초기화합니다.", use_container_width=True):
        st.session_state.home_messages = []

# 새 챗봇 만들기 페이지
def show_create_chatbot_page():
    st.title("새 챗봇 만들기")
    
    # 파일 업로드 섹션 추가
    st.header("📂 파일 업로드하여 챗봇 생성")
    
    uploaded_file = st.file_uploader("파일을 업로드하세요 (PDF, DOCX, TXT 형식)", type=['pdf', 'docx', 'txt'])
    
    if uploaded_file is not None:
        if st.session_state.user["username"] in ['admin', '신병철']:
            with st.spinner("파일을 처리하고 있습니다..."):
                # 파일 처리 로직
                file_extension = uploaded_file.name.split('.')[-1].lower()
                if file_extension == 'pdf':
                    loader = PyPDFLoader(uploaded_file)
                elif file_extension == 'docx':
                    loader = Docx2txtLoader(uploaded_file)
                elif file_extension == 'txt':
                    loader = TextLoader(uploaded_file)
                else:
                    st.error("지원되지 않는 파일 형식입니다.")
                    st.stop()
    
                documents = loader.load()
    
                # Pinecone 초기화
                pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
    
                index_name = 'teacher'
    
                # 인덱스 존재 여부 확인
                if index_name not in pinecone.list_indexes():
                    st.error(f"Pinecone 인덱스 '{index_name}'가 존재하지 않습니다.")
                    st.stop()
    
                # 임베딩 생성
                embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    
                # 벡터스토어에 문서 삽입
                vectorstore = Pinecone.from_documents(documents, embeddings, index_name=index_name)
    
                st.success("파일이 성공적으로 업로드되고 처리되었습니다.")
    
                # 새로운 챗봇 생성
                new_chatbot = {
                    "name": uploaded_file.name,
                    "description": "업로드된 문서를 기반으로 답변하는 챗봇입니다.",
                    "system_prompt": "사용자의 질문에 업로드된 문서의 내용을 바탕으로 답변하세요.",
                    "welcome_message": "안녕하세요! 업로드된 문서를 바탕으로 질문에 답변해 드립니다.",
                    "messages": [],
                    "creator": st.session_state.user["username"],
                    "is_shared": False,
                    "background_color": "#FFFFFF",
                    "profile_image_url": "https://via.placeholder.com/100",
                    "vectorstore_index": index_name
                }
    
                # 챗봇에 고유 ID 추가
                new_chatbot['_id'] = ObjectId()
                db.users.update_one(
                    {"username": st.session_state.user["username"]},
                    {"$push": {"chatbots": new_chatbot}},
                    upsert=True
                )
                # 사용자 정보 갱신
                st.session_state.user = db.users.find_one({"username": st.session_state.user["username"]})
                st.success(f"'{uploaded_file.name}' 챗봇이 생성되었습니다!")
    
                # 생성된 챗봇으로 이동
                st.session_state.current_chatbot = len(st.session_state.user['chatbots']) - 1
                st.session_state.current_page = 'chatbot'
                st.rerun()
        else:
            st.warning("권한이 있는 선생님만 파일 업로드를 할 수 있습니다.(비싸요ㅠ)")

    chatbot_name = st.text_input("챗봇 이름")
    chatbot_description = st.text_input("챗봇 소개")
    system_prompt = st.text_area("시스템 프롬프트", value=
"""역할 : 당신의 역할은 {}이다.
규칙 : 다음 규칙을 따라 사용자에게 답변한다.
- {내용1}
- {내용2}
- {내용3}""", height=300)
    welcome_message = st.text_input("웰컴 메시지", value="안녕하세요! 무엇을 도와드릴까요?")
    is_shared = st.checkbox("다른 교사와 공유하기")
    background_color = st.color_picker("챗봇 카드 배경색 선택", "#FFFFFF")

    if 'temp_profile_image_url' not in st.session_state:
        st.session_state.temp_profile_image_url = "https://via.placeholder.com/100"

    profile_image_url = st.session_state.temp_profile_image_url

    if is_shared:
        # 기존 범주 가져오기
        if db is not None:
            existing_categories = db.shared_chatbots.distinct('category')
        else:
            existing_categories = []
        category_option = st.selectbox('챗봇 범주 선택', options=existing_categories + ['새 범주 입력'])
        if category_option == '새 범주 입력':
            category = st.text_input('새 범주 입력')
        else:
            category = category_option
    else:
        category = None

    if st.button("프로필 이미지 생성"):
        with st.spinner("프로필 이미지를 생성 중입니다. 잠시만 기다려주세요..."):
            profile_image_prompt = f"Create a profile image for a chatbot named '{chatbot_name}'. Description: {chatbot_description}"
            generated_image_url = generate_image(profile_image_prompt)
            if generated_image_url:
                st.session_state.temp_profile_image_url = generated_image_url
                st.success("프로필 이미지가 생성되었습니다.")
            else:
                st.error("프로필 이미지 생성에 실패했습니다. 기본 이미지가 사용됩니다.")

    # 프로필 이미지 표시
    st.image(st.session_state.temp_profile_image_url, caption="프로필 이미지", width=200)

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
            "profile_image_url": st.session_state.temp_profile_image_url
        }
        if is_shared:
            new_chatbot['category'] = category  # 범주 추가

        if db is not None:
            try:
                if is_shared:
                    result = db.shared_chatbots.insert_one(new_chatbot)
                    new_chatbot['_id'] = result.inserted_id
                else:
                    # 챗봇에 고유 ID 추가
                    new_chatbot['_id'] = ObjectId()
                    db.users.update_one(
                        {"username": st.session_state.user["username"]},
                        {"$push": {"chatbots": new_chatbot}},
                        upsert=True
                    )
                    # 사용자 정보 갱신
                    st.session_state.user = db.users.find_one({"username": st.session_state.user["username"]})
                st.success(f"'{chatbot_name}' 챗봇이 생성되었습니다!")
                # 임시 프로필 이미지 URL 초기화
                st.session_state.pop('temp_profile_image_url', None)
                # 새로 생성된 챗봇으로 이동
                if is_shared:
                    st.session_state.current_shared_chatbot = new_chatbot
                    st.session_state.current_page = 'shared_chatbot'
                else:
                    st.session_state.current_chatbot = len(st.session_state.user['chatbots']) - 1
                    st.session_state.current_page = 'chatbot'
                st.rerun()
            except Exception as e:
                st.error(f"챗봇 생성 중 오류가 발생했습니다: {str(e)}")
        else:
            if 'chatbots' not in st.session_state.user:
                st.session_state.user['chatbots'] = []
            st.session_state.user['chatbots'].append(new_chatbot)
            st.success(f"'{chatbot_name}' 챗봇이 생성되었습니다! (오프라인 모드)")
            # 임시 프로필 이미지 URL 초기화
            st.session_state.pop('temp_profile_image_url', None)
            # 새로 생성된 챗봇으로 이동
            st.session_state.current_chatbot = len(st.session_state.user['chatbots']) - 1
            st.session_state.current_page = 'chatbot'
            st.rerun()

# 챗봇 수정 페이지
def show_edit_chatbot_page():
    st.title("챗봇 수정")

    if 'editing_chatbot' not in st.session_state:
        st.error("수정할 챗봇이 선택되지 않았습니다.")
        return

    chatbot = st.session_state.user["chatbots"][st.session_state.editing_chatbot]

    new_name = st.text_input("챗봇 이름", value=chatbot['name'])
    new_description = st.text_input("챗봇 소개", value=chatbot['description'])
    new_system_prompt = st.text_area("시스템 프롬프트", value=chatbot['system_prompt'], height=200)
    new_welcome_message = st.text_input("웰컴 메시지", value=chatbot['welcome_message'])
    new_background_color = st.color_picker("챗봇 카드 배경색 선택", value=chatbot.get('background_color', '#FFFFFF'))

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
    else:
        # 기존 프로필 이미지 표시
        st.image(chatbot.get('profile_image_url', 'https://via.placeholder.com/100'), caption="현재 프로필 이미지", width=200)

    if st.button("변경 사항 저장"):
        chatbot['name'] = new_name
        chatbot['description'] = new_description
        chatbot['system_prompt'] = new_system_prompt
        chatbot['welcome_message'] = new_welcome_message
        chatbot['background_color'] = new_background_color

        if db is not None:
            try:
                db.users.update_one(
                    {"username": st.session_state.user["username"]},
                    {"$set": {f"chatbots.{st.session_state.editing_chatbot}": chatbot}}
                )
                st.success("챗봇이 성공적으로 수정되었습니다.")
                st.session_state.current_chatbot = st.session_state.editing_chatbot
                st.session_state.pop('editing_chatbot', None)
                st.session_state.current_page = 'chatbot'
                st.rerun()
            except Exception as e:
                st.error(f"챗봇 수정 중 오류가 발생했습니다: {str(e)}")
        else:
            st.session_state.user['chatbots'][st.session_state.editing_chatbot] = chatbot
            st.success("챗봇이 성공적으로 수정되었습니다. (오프라인 모드)")
            st.session_state.current_chatbot = st.session_state.editing_chatbot
            st.session_state.pop('editing_chatbot', None)
            st.session_state.current_page = 'chatbot'
            st.rerun()

# 대화 내역 저장 함수 (공개 챗봇용)
def save_public_chat_history(chatbot_id, user_name, messages):
    if db is not None:
        try:
            chat_history = {
                "chatbot_id": str(chatbot_id),
                "user_name": user_name,
                "timestamp": datetime.now(),
                "messages": messages
            }
            db.public_chat_history.insert_one(chat_history)
        except Exception as e:
            st.error(f"대화 내역 저장 중 오류가 발생했습니다: {str(e)}")

# 나만 사용 가능한 챗봇 페이지
def show_available_chatbots_page():
    st.title("나만 사용 가능한 챗봇")
    if db is not None and st.session_state.user["username"] == 'admin':
        # admin user can see all chatbots
        users = db.users.find()
        all_chatbots = []
        for user in users:
            user_chatbots = user.get("chatbots", [])
            for chatbot in user_chatbots:
                chatbot["owner"] = user["username"]
                all_chatbots.append(chatbot)
        chatbots_to_show = all_chatbots
    else:
        chatbots_to_show = st.session_state.user.get("chatbots", [])

    if not chatbots_to_show:
        st.info("아직 만든 챗봇이 없습니다. '새 챗봇 만들기'에서 첫 번째 챗봇을 만들어보세요!")
        return

    # st.secrets에서 BASE_URL 가져오기
    try:
        base_url = st.secrets["BASE_URL"]
    except KeyError:
        st.error("BASE_URL이 설정되지 않았습니다. Streamlit secrets에 BASE_URL을 추가해주세요.")
        return

    cols = st.columns(3)
    for i, chatbot in enumerate(chatbots_to_show):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="chatbot-card" style="background-color: {chatbot.get('background_color', '#FFFFFF')}">
                <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/100')}" alt="프로필 이미지">
                <div class="chatbot-info">
                    <div class="chatbot-name">{chatbot['name']}</div>
                    <div class="chatbot-description">{chatbot['description']}</div>
            """, unsafe_allow_html=True)
            if st.session_state.user["username"] == 'admin' and 'owner' in chatbot:
                st.markdown(f"<p>소유자: {chatbot['owner']}</p>", unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("사용하기", key=f"use_{i}"):
                    st.session_state.current_chatbot = i
                    st.session_state.current_page = 'chatbot'
                    st.rerun()
            with col2:
                if st.session_state.user["username"] == 'admin' or chatbot.get('creator', '') == st.session_state.user["username"]:
                    if st.button("수정하기", key=f"edit_{i}"):
                        st.session_state.editing_chatbot = i
                        st.session_state.current_page = 'edit_chatbot'
                        st.rerun()
            with col3:
                if st.session_state.user["username"] == 'admin' or chatbot.get('creator', '') == st.session_state.user["username"]:
                    if st.button("삭제하기", key=f"delete_{i}"):
                        if delete_chatbot(chatbot.get('_id'), chatbot.get('creator', '')):
                            st.success(f"'{chatbot['name']}' 챗봇이 삭제되었습니다.")
                            st.rerun()
            # URL 생성 버튼 추가
            with st.expander("URL 생성", expanded=False):
                selected_model = st.selectbox("모델 선택", MODEL_OPTIONS, key=f"model_select_{i}")
                if st.button("URL 생성", key=f"generate_url_{i}"):
                    chatbot_id = str(chatbot.get('_id', i))
                    # 모델 이름을 URL 인코딩
                    model_param = urllib.parse.quote(selected_model)
                    shareable_url = f"{base_url}?chatbot_id={chatbot_id}&model={model_param}"
                    st.write(f"공유 가능한 URL: {shareable_url}")

                    # QR 코드 생성
                    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(shareable_url)}"
                    qr_code_response = requests.get(qr_code_url)
                    if qr_code_response.status_code == 200:
                        qr_code_image = qr_code_response.content
                        # 이미지 표시
                        st.markdown("<div class='qr-code'>", unsafe_allow_html=True)
                        st.image(qr_code_image, caption="QR 코드 (클릭하여 확대)", use_column_width=False)
                        st.markdown("</div>", unsafe_allow_html=True)
                        # 이미지 확대 기능
                        if st.button("QR 코드 확대", key=f"enlarge_qr_{i}"):
                            st.image(qr_code_image, caption="QR 코드 (전체화면)", use_column_width=True)
                    else:
                        st.error("QR 코드를 생성하는 데 실패했습니다.")

            # 챗봇 제작자만 볼 수 있는 'URL 사용자 대화내역 보기' 버튼 추가
            if chatbot.get('creator', '') == st.session_state.user["username"] or st.session_state.user["username"] == 'admin':
                if st.button("URL 사용자 대화내역 보기", key=f"view_url_history_{i}"):
                    st.session_state.viewing_chatbot_history = str(chatbot['_id'])
                    st.session_state.current_page = 'view_public_chat_history'
                    st.rerun()

# 챗봇 삭제 함수 수정
def delete_chatbot(chatbot_id, creator):
    if db is not None:
        try:
            if st.session_state.user["username"] == 'admin' or creator == st.session_state.user["username"]:
                db.users.update_one(
                    {"chatbots._id": ObjectId(chatbot_id)},
                    {"$pull": {"chatbots": {"_id": ObjectId(chatbot_id)}}}
                )
                # 관련된 대화 내역도 삭제
                db.chat_history.delete_many({"chatbot_name": chatbot_id})
                db.public_chat_history.delete_many({"chatbot_id": str(chatbot_id)})
                st.session_state.user = db.users.find_one({"username": st.session_state.user["username"]})
                return True
            else:
                st.error("삭제 권한이 없습니다.")
                return False
        except Exception as e:
            st.error(f"챗봇 삭제 중 오류가 발생했습니다: {str(e)}")
            return False
    else:
        st.session_state.user["chatbots"] = [cb for cb in st.session_state.user["chatbots"] if cb.get('_id') != chatbot_id]
        return True

# 공유 챗봇 페이지
def show_shared_chatbots_page():
    st.title("수원외국어고등학교 공유 챗봇")
    if db is not None:
        shared_chatbots = list(db.shared_chatbots.find())
        if not shared_chatbots:
            st.info("공유된 챗봇이 없습니다.")
            return

        # 범주별로 챗봇 그룹화
        categories = {}
        for chatbot in shared_chatbots:
            category = chatbot.get('category', '기타')
            if category not in categories:
                categories[category] = []
            categories[category].append(chatbot)

        for category, chatbots_in_category in categories.items():
            st.subheader(f"범주: {category}")
            cols = st.columns(3)
            for i, chatbot in enumerate(chatbots_in_category):
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
                        if st.button("사용하기", key=f"use_shared_{category}_{i}"):
                            st.session_state.current_shared_chatbot = chatbot
                            st.session_state.current_page = 'shared_chatbot'
                            st.rerun()
                    with col2:
                        if chatbot['creator'] == st.session_state.user["username"] or st.session_state.user["username"] == 'admin':
                            if st.button("수정하기", key=f"edit_shared_{category}_{i}"):
                                st.session_state.editing_shared_chatbot = chatbot
                                st.session_state.current_page = 'edit_shared_chatbot'
                                st.rerun()
                    with col3:
                        if chatbot['creator'] == st.session_state.user["username"] or st.session_state.user["username"] == 'admin':
                            if st.button("삭제하기", key=f"delete_shared_{category}_{i}"):
                                if delete_shared_chatbot(chatbot['_id']):
                                    st.success(f"'{chatbot['name']}' 공유 챗봇이 삭제되었습니다.")
                                    st.rerun()
    else:
        st.write("데이터베이스 연결이 없어 공유 챗봇을 불러올 수 없습니다.")

# 공유 챗봇 삭제 함수 수정
def delete_shared_chatbot(chatbot_id):
    if db is not None:
        try:
            if st.session_state.user["username"] == 'admin':
                result = db.shared_chatbots.delete_one({"_id": chatbot_id})
            else:
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

    new_name = st.text_input("챗봇 이름", value=chatbot['name'])
    new_description = st.text_input("챗봇 소개", value=chatbot['description'])
    new_system_prompt = st.text_area("시스템 프롬프트", value=chatbot['system_prompt'], height=200)
    new_welcome_message = st.text_input("웰컴 메시지", value=chatbot['welcome_message'])
    new_background_color = st.color_picker("챗봇 카드 배경색 선택", value=chatbot.get('background_color', '#FFFFFF'))

    # 범주 수정
    if db is not None:
        existing_categories = db.shared_chatbots.distinct('category')
    else:
        existing_categories = []
    category_option = st.selectbox('챗봇 범주 선택', options=existing_categories + ['새 범주 입력'], index=existing_categories.index(chatbot.get('category', '기타')) if chatbot.get('category', '기타') in existing_categories else len(existing_categories))
    if category_option == '새 범주 입력':
        new_category = st.text_input('새 범주 입력', value=chatbot.get('category', ''))
    else:
        new_category = category_option

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
    else:
        # 기존 프로필 이미지 표시
        st.image(chatbot.get('profile_image_url', 'https://via.placeholder.com/100'), caption="현재 프로필 이미지", width=200)

    if st.button("변경 사항 저장"):
        chatbot['name'] = new_name
        chatbot['description'] = new_description
        chatbot['system_prompt'] = new_system_prompt
        chatbot['welcome_message'] = new_welcome_message
        chatbot['background_color'] = new_background_color
        chatbot['category'] = new_category

        if db is not None:
            try:
                db.shared_chatbots.update_one(
                    {"_id": chatbot["_id"]},
                    {"$set": chatbot}
                )
                st.success("공유 챗봇이 성공적으로 수정되었습니다.")
                st.session_state.current_shared_chatbot = chatbot
                st.session_state.pop('editing_shared_chatbot', None)
                st.session_state.current_page = 'shared_chatbot'
                st.rerun()
            except Exception as e:
                st.error(f"공유 챗봇 수정 중 오류가 발생했습니다: {str(e)}")
        else:
            st.error("데이터베이스 연결이 없어 공유 챗봇을 수정할 수 없습니다.")

# 특정 챗봇 페이지
def show_chatbot_page():
    if db is not None and st.session_state.user["username"] == 'admin':
        # admin user can access any chatbot
        users = db.users.find()
        all_chatbots = []
        for user in users:
            user_chatbots = user.get("chatbots", [])
            for chatbot in user_chatbots:
                all_chatbots.append(chatbot)
        chatbot = all_chatbots[st.session_state.current_chatbot]
    else:
        chatbot = st.session_state.user["chatbots"][st.session_state.current_chatbot]

    # 제목과 프로필 이미지를 함께 표시
    st.markdown(f"""
    <div class="chatbot-title">
        <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/150')}" alt="프로필 이미지">
        <h1>{chatbot['name']} 챗봇</h1>
    </div>
    """, unsafe_allow_html=True)

    # 수정 버튼 클릭 처리
    if chatbot.get('creator', '') == st.session_state.user["username"] or st.session_state.user["username"] == 'admin':
        st.markdown('<div class="small-button">', unsafe_allow_html=True)
        if st.button("수정", key="edit_button"):
            st.session_state.editing_chatbot = st.session_state.current_chatbot
            st.session_state.current_page = 'edit_chatbot'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

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
                    start_time = datetime.now()

                    
                    # 벡터스토어를 사용하는 챗봇인지 확인
                    if 'vectorstore_index' in chatbot:
                        # Pinecone 초기화
                        pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
                        index_name = chatbot['vectorstore_index']
    
                        # 임베딩 및 벡터스토어 설정
                        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
                        vectorstore = Pinecone(index_name, embeddings.embed_query, "text")
    
                        # LLM 설정
                        from langchain.llms import OpenAI
                        llm = OpenAI(openai_api_key=OPENAI_API_KEY, model_name=selected_model)
    
                        # RetrievalQA 체인 생성
                        from langchain.chains import RetrievalQA
                        qa_chain = RetrievalQA.from_chain_type(llm=llm, chain_type='stuff', retriever=vectorstore.as_retriever())
    
                        # 답변 생성
                        response = qa_chain.run(prompt)
                        full_response = response
                        message_placeholder.markdown(full_response)
    
                        # 사용량 기록
                        record_usage(st.session_state.user["username"], 'vectorstore', start_time)
                    elif "gemini" in selected_model:
                        model = genai.GenerativeModel(selected_model)
                        response = model.generate_content(chatbot['system_prompt'] + "\n\n" + prompt, stream=True)
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                message_placeholder.markdown(full_response + "▌")
                        record_usage(st.session_state.user["username"], selected_model, start_time)
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
                        record_usage(st.session_state.user["username"], selected_model, start_time)
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
        <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/150')}" alt="프로필 이미지">
        <h1>{chatbot['name']} (공유 챗봇)</h1>
    </div>
    """, unsafe_allow_html=True)

    # 수정 버튼 클릭 처리
    if chatbot['creator'] == st.session_state.user["username"] or st.session_state.user["username"] == 'admin':
        st.markdown('<div class="small-button">', unsafe_allow_html=True)
        if st.button("수정", key="edit_button"):
            st.session_state.editing_shared_chatbot = chatbot
            st.session_state.current_page = 'edit_shared_chatbot'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    selected_model = st.sidebar.selectbox("모델 선택", MODEL_OPTIONS)

    # 사이드바에 대화 내역 초기화 버튼 추가
    if st.sidebar.button("현재 대화내역 초기화", key="reset_chat", help="현재 대화 내역을 초기화합니다.", use_container_width=True):
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
                    start_time = datetime.now()
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
                        # 사용량 기록
                        record_usage(st.session_state.user["username"], selected_model, start_time)
                    elif "gemini" in selected_model:
                        model = genai.GenerativeModel(selected_model)
                        response = model.generate_content(chatbot['system_prompt'] + "\n\n" + prompt, stream=True)
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                message_placeholder.markdown(full_response + "▌")
                        record_usage(st.session_state.user["username"], selected_model, start_time)
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
                        record_usage(st.session_state.user["username"], selected_model, start_time)
                except Exception as e:
                    st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")

                if full_response:
                    chatbot['messages'].append({"role": "assistant", "content": full_response})

# 비로그인 사용자용 챗봇 페이지 함수 수정
def show_public_chatbot_page(chatbot_id):
    # 챗봇 불러오기
    chatbot = None
    if db is not None:
        user = db.users.find_one({"chatbots._id": ObjectId(chatbot_id)}, {"chatbots.$": 1})
        if user:
            chatbot = user['chatbots'][0]
    else:
        st.error("데이터베이스 연결이 필요합니다.")
        return

    if not chatbot:
        st.error("챗봇을 찾을 수 없습니다.")
        return

    # URL에서 모델 파라미터 가져오기
    query_params = st.query_params
    selected_model = query_params.get('model', ['gpt-4o'])[0]

    # 챗봇 이름과 프로필 이미지 표시
    st.markdown(f"""
    <div class="chatbot-title">
        <img src="{chatbot.get('profile_image_url', 'https://via.placeholder.com/150')}" alt="프로필 이미지">
        <h1>{chatbot['name']}</h1>
    </div>
    """, unsafe_allow_html=True)

    if 'user_name' not in st.session_state:
        name = st.text_input("이름을 입력하세요")
        start_button_clicked = st.button("챗봇 시작하기")
        if name and start_button_clicked:
            st.session_state.user_name = name
            # st.rerun()을 제거하고 세션 상태에 따라 진행
    if 'user_name' in st.session_state:
        # 대화 시작
        start_chatting(chatbot, st.session_state.user_name, selected_model)

# 대화 시작 함수 수정
def start_chatting(chatbot, user_name, selected_model):
    if 'public_chatbot_messages' not in st.session_state:
        st.session_state.public_chatbot_messages = [{"role": "assistant", "content": chatbot.get('welcome_message', "안녕하세요! 무엇을 도와드릴까요?")}]

    for message in st.session_state.public_chatbot_messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "image_url" in message:
                st.image(message["image_url"], caption="생성된 이미지")
            st.markdown(message["content"])

    if prompt := st.chat_input("무엇을 도와드릴까요?"):
        st.session_state.public_chatbot_messages.append({"role": "user", "content": prompt})
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
                        st.session_state.public_chatbot_messages.append({"role": "assistant", "content": full_response, "image_url": image_url})
                    else:
                        full_response = "죄송합니다. 이미지 생성 중 오류가 발생했습니다. 다른 주제로 시도해 보시거나, 요청을 더 구체적으로 해주세요."
            else:
                try:
                    start_time = datetime.now()
                    if "gpt" in selected_model:
                        response = openai_client.chat.completions.create(
                            model=selected_model,
                            messages=[{"role": "system", "content": chatbot['system_prompt']}] + st.session_state.public_chatbot_messages,
                            stream=True
                        )
                        for chunk in response:
                            if chunk.choices[0].delta.content is not None:
                                full_response += chunk.choices[0].delta.content
                                message_placeholder.markdown(full_response + "▌")
                        # 사용량 기록: 챗봇 제작자의 이름으로 기록
                        record_usage(chatbot['creator'], selected_model, start_time)
                    elif "gemini" in selected_model:
                        model = genai.GenerativeModel(selected_model)
                        response = model.generate_content(chatbot['system_prompt'] + "\n\n" + prompt, stream=True)
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                message_placeholder.markdown(full_response + "▌")
                        record_usage(chatbot['creator'], selected_model, start_time)
                    elif "claude" in selected_model:
                        with anthropic_client.messages.stream(
                            max_tokens=1000,
                            messages=st.session_state.public_chatbot_messages,
                            model=selected_model,
                            system=chatbot['system_prompt'],
                        ) as stream:
                            for text in stream.text_stream:
                                full_response += text
                                message_placeholder.markdown(full_response + "▌")
                        record_usage(chatbot['creator'], selected_model, start_time)
                except Exception as e:
                    st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")

                # 대화 내역에 추가
                if full_response:
                    st.session_state.public_chatbot_messages.append({"role": "assistant", "content": full_response})
                    message_placeholder.markdown(full_response)

            # 대화 내역 저장
            save_public_chat_history(chatbot['_id'], user_name, st.session_state.public_chatbot_messages)

# 대화 내역 확인 페이지
def show_chat_history_page():
    st.title("대화 내역 확인")

    if 'user' in st.session_state and st.session_state.user:
        for i, chatbot in enumerate(st.session_state.user.get('chatbots', [])):
            st.subheader(f"{i+1}. {chatbot['name']}")
            st.write(chatbot['description'])
            if st.button(f"개인 대화 내역 보기 #{i}"):
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

            if st.button(f"공개 대화 내역 보기 #{i}"):
                if db is not None:
                    st.write("--- 공개 대화 내역 ---")
                    chat_histories = db.public_chat_history.find({
                        "chatbot_id": str(chatbot.get('_id'))
                    }).sort("timestamp", -1)

                    for history in chat_histories:
                        st.write(f"사용자 이름: {history['user_name']}")
                        st.write(f"대화 시간: {history['timestamp']}")
                        for message in history['messages']:
                            st.write(f"{message['role']}: {message['content']}")
                        st.write("---")
                else:
                    st.warning("데이터베이스 연결이 없어 공개 대화 내역을 불러올 수 없습니다.")
    else:
        st.warning("로그인이 필요합니다.")

# 특정 대화 내역 삭제 함수
def delete_specific_chat_history(history_id):
    if db is not None:
        try:
            db.chat_history.delete_one({"_id": history_id})
        except Exception as e:
            st.error(f"대화 내역 삭제 중 오류가 발생했습니다: {str(e)}")

# URL 사용자 대화내역 보기 함수 수정
def show_public_chatbot_history():
    st.title("URL 사용자 대화내역")

    chatbot_id = str(st.session_state.viewing_chatbot_history)

    # 챗봇 정보 가져오기 및 제작자 확인
    user = db.users.find_one(
        {"chatbots._id": ObjectId(chatbot_id)},
        {"chatbots.$": 1}
    )
    if user:
        chatbot = user['chatbots'][0]
        if chatbot.get('creator', '') != st.session_state.user["username"] and st.session_state.user["username"] != 'admin':
            st.error("해당 챗봇의 대화 내역을 볼 권한이 없습니다.")
            return
    else:
        st.error("챗봇을 찾을 수 없습니다.")
        return

    if db is not None:
        # 사용자 이름 목록 가져오기
        user_names = db.public_chat_history.distinct("user_name", {"chatbot_id": chatbot_id})

        if not user_names:
            st.info("아직 대화 내역이 없습니다.")
            return

        selected_user = st.selectbox("사용자 선택", sorted(user_names))

        if selected_user:
            # 선택한 사용자에 대한 대화 내역 가져오기
            chat_histories = db.public_chat_history.find({
                "chatbot_id": chatbot_id,
                "user_name": selected_user
            }).sort("timestamp", 1)  # 오름차순 정렬

            all_messages = []
            first_timestamp = None

            for history in chat_histories:
                if first_timestamp is None:
                    first_timestamp = history['timestamp']
                all_messages.extend(history['messages'])

            if first_timestamp:
                st.write(f"대화 시작 시간: {first_timestamp}")
            else:
                st.write("대화 내역이 없습니다.")

            for message in all_messages:
                st.write(f"{message['role']}: {message['content']}")
            st.write("---")
    else:
        st.warning("데이터베이스 연결이 없어 대화 내역을 불러올 수 없습니다.")

# 사용량 데이터 페이지 추가
def show_usage_data_page():
    st.title("AI 모델 사용량 데이터")

    if db is not None:
        usage_logs = list(db.usage_logs.find())

        if not usage_logs:
            st.info("사용량 데이터가 없습니다.")
            return

        df = pd.DataFrame(usage_logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date

        # 필터링 및 정렬 기능 추가
        usernames = df['username'].unique()
        selected_user = st.multiselect("사용자 선택", usernames, default=usernames)
        models = df['model_name'].unique()
        selected_model = st.multiselect("모델 선택", models, default=models)
        date_range = st.date_input("날짜 범위 선택", [])
        if len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        df_filtered = df[(df['username'].isin(selected_user)) & (df['model_name'].isin(selected_model))]

        # 데이터 표시
        st.dataframe(df_filtered[['username', 'model_name', 'timestamp', 'tokens_used']])

        # 사용자별 모델 사용 횟수 집계
        usage_summary = df_filtered.groupby(['username', 'model_name']).size().reset_index(name='사용 횟수')
        st.write("사용자별 모델 사용 횟수:")
        st.dataframe(usage_summary)
    else:
        st.warning("데이터베이스 연결이 없어 사용량 데이터를 불러올 수 없습니다.")

# 메인 애플리케이션
def main_app():
    # 사이드바 메뉴
    st.sidebar.title("메뉴")
    menu_items = [
        ("홈", 'home'),
        ("새 챗봇 만들기", 'create_chatbot'),
        ("나만 사용 가능한 챗봇", 'available_chatbots'),
        ("수원외국어고등학교 공유 챗봇", 'shared_chatbots'),
        ("대화 내역 확인", 'chat_history'),
    ]

    # 관리자일 경우 사용량 데이터 메뉴 추가
    if st.session_state.user["username"] == 'admin':
        menu_items.append(("사용량 데이터", 'usage_data'))

    menu_items.append(("로그아웃", 'logout'))

    for label, page in menu_items:
        if st.sidebar.button(label, key=f"menu_{page}", use_container_width=True):
            if page == 'logout':
                st.session_state.user = None
                st.session_state.current_page = 'login'
                st.rerun()
            else:
                st.session_state.current_page = page

            st.rerun()  # 페이지 갱신

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
    elif st.session_state.current_page == 'view_public_chat_history':
        show_public_chatbot_history()
    elif st.session_state.current_page == 'usage_data':
        show_usage_data_page()
    else:
        st.session_state.current_page = 'home'
        show_home_page()

    # 오래된 대화 내역 삭제 (1달 이상 된 내역)
    delete_old_chat_history()

    # 사이드바 맨 아래에 작은 글씨 추가
    add_sidebar_footer()

# 사이드바 맨 아래에 작은 글씨 추가하는 함수
def add_sidebar_footer():
    st.sidebar.markdown("""
    ---
    <small>제작 : 수원외고 교사 신병철(sinbc2004@naver.com)</small>
    """, unsafe_allow_html=True)

# 메인 실행 부분
def main():
    query_params = st.query_params
    if 'chatbot_id' in query_params:
        chatbot_id = query_params['chatbot_id'][0]
        show_public_chatbot_page(chatbot_id)
    elif st.session_state.current_page == 'login':
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
