import os
import re
import requests
import json
import traceback
import base64
import io
import urllib.parse
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson.objectid import ObjectId
from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai
from google.oauth2.service_account import Credentials
import gspread
from google.auth.exceptions import GoogleAuthError
from google.cloud import storage

# 전역 변수 선언
db = None
anthropic_client = None
openai_client = None
gs_client = None
sheet = None
storage_client = None

# 모델 선택 옵션
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

def connect_to_mongo():
    global db
    try:
        MONGO_URI = os.environ.get("MONGO_URI")
        client = MongoClient(MONGO_URI)
        db = client.get_database("chatbot_platform")
    except Exception as e:
        print("데이터베이스 연결에 실패했습니다. 관리자에게 문의해주세요.")
        db = None

def initialize_api_clients():
    global anthropic_client, openai_client, genai
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

    if not (ANTHROPIC_API_KEY and OPENAI_API_KEY and GEMINI_API_KEY):
        print("하나 이상의 API 키가 설정되지 않았습니다. 환경 변수를 확인해주세요.")
        exit()

    try:
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print("API 클라이언트 초기화에 실패했습니다. 관리자에게 문의해주세요.")
        exit()

def initialize_google_services():
    global gs_client, sheet, storage_client
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/devstorage.read_write'
        ]
        service_account_info = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
        service_account_info = json.loads(service_account_info)

        creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
        gs_client = gspread.authorize(creds)

        storage_client = storage.Client(credentials=creds, project=service_account_info['project_id'])

        sheet_url = "https://docs.google.com/spreadsheets/d/your_spreadsheet_id/edit?gid=0"
        sheet = gs_client.open_by_url(sheet_url).sheet1
    except GoogleAuthError as e:
        print(f"Google 인증 오류: {str(e)}")
        sheet = None
    except Exception as e:
        print(f"Google Sheets 설정 중 오류가 발생했습니다: {str(e)}")
        print(traceback.format_exc())
        sheet = None

def is_image_request(text):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in IMAGE_PATTERNS)

def upload_image_to_gcs(image_data, filename):
    try:
        bucket_name = 'sawlteacher'
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_data, content_type='image/png')
        public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
        return public_url
    except Exception as e:
        print(f"이미지를 Cloud Storage에 업로드하는 중 오류가 발생했습니다: {str(e)}")
        return None

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
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            image_data = image_response.content
            filename = f"images/{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
            public_url = upload_image_to_gcs(image_data, filename)
            if public_url:
                return public_url
            else:
                return None
        else:
            print("이미지 다운로드에 실패했습니다.")
            return None
    except Exception as e:
        print(f"이미지 생성에 실패했습니다. 다시 시도해주세요. 오류: {str(e)}")
        return None

def get_users_data():
    if sheet is None:
        print("Google Sheets 연결에 실패하여 사용자 데이터를 불러올 수 없습니다.")
        return None
    try:
        values = sheet.get_all_values()
        if not values:
            print("스프레드시트에 데이터가 없습니다.")
            return None
        headers = [header.strip() for header in values[0]]
        data_rows = values[1:]
        records = []
        for row in data_rows:
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            record = dict(zip(headers, row))
            records.append(record)
        return records
    except Exception as e:
        print(f"사용자 데이터 불러오기 중 오류가 발생했습니다: {str(e)}")
        return None

def login(username, password):
    users_data = get_users_data()
    if users_data is None:
        print("사용자 데이터를 불러올 수 없어 로그인할 수 없습니다.")
        return None

    try:
        if not users_data:
            print("사용자 데이터가 비어 있습니다.")
            return None

        first_row_keys = list(users_data[0].keys())
        lower_keys = [key.lower() for key in first_row_keys]

        if '아이디' in lower_keys:
            id_key = first_row_keys[lower_keys.index('아이디')]
        else:
            print("스프레드시트에 '아이디' 열이 없습니다.")
            return None

        if '비밀번호' in lower_keys:
            password_key = first_row_keys[lower_keys.index('비밀번호')]
        else:
            print("스프레드시트에 '비밀번호' 열이 없습니다.")
            return None

        for row in users_data:
            if row.get(id_key) == username:
                if row.get(password_key) == password:
                    if password == "1111":
                        return "change_password"
                    if db is not None:
                        user = db.users.find_one({"username": username})
                        if user:
                            return user
                        else:
                            new_user = {"username": username, "chatbots": []}
                            db.users.insert_one(new_user)
                            return new_user
                    else:
                        return {"username": username, "chatbots": []}
                else:
                    print("비밀번호가 잘못되었습니다.")
                    return None
        else:
            print("아이디를 찾을 수 없습니다.")
            return None
    except Exception as e:
        print(f"로그인 중 오류가 발생했습니다: {str(e)}")
    return None

def change_password(username, new_password):
    users_data = get_users_data()
    if users_data is None:
        print("사용자 데이터를 불러올 수 없어 비밀번호를 변경할 수 없습니다.")
        return False

    try:
        if not users_data:
            print("사용자 데이터가 비어 있습니다.")
            return False

        first_row_keys = list(users_data[0].keys())
        lower_keys = [key.lower() for key in first_row_keys]

        if '아이디' in lower_keys:
            id_key = first_row_keys[lower_keys.index('아이디')]
        else:
            print("스프레드시트에 '아이디' 열이 없습니다.")
            return False

        if '비밀번호' in lower_keys:
            password_key = first_row_keys[lower_keys.index('비밀번호')]
        else:
            print("스프레드시트에 '비밀번호' 열이 없습니다.")
            return False

        for idx, row in enumerate(users_data):
            if row.get(id_key) == username:
                row_number = idx + 2
                col_number = lower_keys.index('비밀번호') + 1
                sheet.update_cell(row_number, col_number, new_password)
                return True
        else:
            return False
    except Exception as e:
        print(f"비밀번호 변경 중 오류가 발생했습니다: {str(e)}")
        return False

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
            print(f"대화 내역 저장 중 오류가 발생했습니다: {str(e)}")

def delete_old_chat_history():
    if db is not None:
        try:
            one_month_ago = datetime.now() - timedelta(days=30)
            db.chat_history.delete_many({"timestamp": {"$lt": one_month_ago}})
            db.public_chat_history.delete_many({"timestamp": {"$lt": one_month_ago}})
            db.usage_logs.delete_many({"timestamp": {"$lt": one_month_ago}})
        except Exception as e:
            print(f"오래된 대화 내역 삭제 중 오류가 발생했습니다: {str(e)}")

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
            print(f"사용량 기록 중 오류가 발생했습니다: {str(e)}")

def delete_specific_chat_history(history_id):
    if db is not None:
        try:
            db.chat_history.delete_one({"_id": history_id})
        except Exception as e:
            print(f"대화 내역 삭제 중 오류가 발생했습니다: {str(e)}")

def connect_services():
    connect_to_mongo()
    initialize_api_clients()
    initialize_google_services()
