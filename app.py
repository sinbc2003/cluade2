import os
from flask import Flask, request, jsonify
from anthropic import Anthropic
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
import json
from google.cloud import storage
import io

app = Flask(__name__)

# 전역 변수로 db 선언
db = None

# MongoDB 연결
try:
    MONGO_URI = os.environ.get("MONGO_URI")
    client = MongoClient(MONGO_URI)
    db = client.get_database("chatbot_platform")
except Exception as e:
    print(f"데이터베이스 연결에 실패했습니다: {str(e)}")
    db = None

# API 키 가져오기
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not (ANTHROPIC_API_KEY and OPENAI_API_KEY and GEMINI_API_KEY):
    raise ValueError("하나 이상의 API 키가 설정되지 않았습니다. 환경 변수를 확인해주세요.")

# API 클라이언트 설정
try:
    anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"API 클라이언트 초기화에 실패했습니다: {str(e)}")
    raise

# Google Sheets API 및 Google Cloud Storage 설정
try:
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/devstorage.read_write'  # Cloud Storage 접근 권한 추가
    ]
    service_account_info = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    service_account_info = json.loads(service_account_info)  # JSON 문자열을 딕셔너리로 변환

    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    gs_client = gspread.authorize(creds)

    # Google Cloud Storage 클라이언트 설정
    try:
        storage_client = storage.Client(credentials=creds, project=service_account_info['project_id'])
    except Exception as e:
        print(f"Google Cloud Storage 클라이언트 초기화에 실패했습니다: {str(e)}")
        storage_client = None

    # 스프레드시트 열기
    sheet_url = "https://docs.google.com/spreadsheets/d/your_spreadsheet_id/edit?gid=0"
    try:
        sheet = gs_client.open_by_url(sheet_url).sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"스프레드시트를 찾을 수 없습니다. URL을 확인해주세요: {sheet_url}")
        sheet = None
    except gspread.exceptions.NoValidUrlKeyFound:
        print(f"올바르지 않은 스프레드시트 URL입니다: {sheet_url}")
        sheet = None
    except gspread.exceptions.APIError as e:
        if 'PERMISSION_DENIED' in str(e):
            print("스프레드시트에 접근할 권한이 없습니다. 서비스 계정 이메일을 스프레드시트의 공유 설정에 추가했는지 확인해주세요.")
        else:
            print(f"Google Sheets API 오류: {str(e)}")
        sheet = None
except GoogleAuthError as e:
    print(f"Google 인증 오류: {str(e)}")
    sheet = None
except Exception as e:
    print(f"Google Sheets 설정 중 오류가 발생했습니다: {str(e)}")
    print(traceback.format_exc())  # 예외의 상세 정보 출력
    sheet = None

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
        # 업로드한 객체의 공개 URL 생성
        public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
        return public_url
    except Exception as e:
        print(f"이미지를 Cloud Storage에 업로드하는 중 오류가 발생했습니다: {str(e)}")
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
            print("이미지 다운로드에 실패했습니다.")
            return None
    except Exception as e:
        print(f"이미지 생성에 실패했습니다. 다시 시도해주세요. 오류: {str(e)}")
        return None

# 사용자 데이터 가져오기 함수
def get_users_data():
    if sheet is None:
        print("Google Sheets 연결에 실패하여 사용자 데이터를 불러올 수 없습니다.")
        return None
    try:
        # 모든 데이터를 가져옵니다.
        values = sheet.get_all_values()
        if not values:
            print("스프레드시트에 데이터가 없습니다.")
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
        print(f"사용자 데이터 불러오기 중 오류가 발생했습니다: {str(e)}")
        return None

# 로그인 함수 수정
def login(username, password):
    users_data = get_users_data()
    if users_data is None:
        return None, "사용자 데이터를 불러올 수 없어 로그인할 수 없습니다."

    try:
        if not users_data:
            return None, "사용자 데이터가 비어 있습니다."

        # 첫 번째 행의 키(헤더)를 가져옵니다.
        first_row_keys = list(users_data[0].keys())
        # 키를 모두 소문자로 변환하여 비교합니다.
        lower_keys = [key.lower() for key in first_row_keys]

        # '아이디'와 '비밀번호' 키가 있는지 확인합니다.
        if '아이디' in lower_keys:
            id_key = first_row_keys[lower_keys.index('아이디')]
        else:
            return None, "스프레드시트에 '아이디' 열이 없습니다."

        if '비밀번호' in lower_keys:
            password_key = first_row_keys[lower_keys.index('비밀번호')]
        else:
            return None, "스프레드시트에 '비밀번호' 열이 없습니다."

        # 사용자 찾기
        for row in users_data:
            if row.get(id_key) == username:
                if row.get(password_key) == password:
                    if password == "1111":
                        return "change_password", None
                    # 데이터베이스에서 사용자 정보 가져오기
                    if db is not None:
                        user = db.users.find_one({"username": username})
                        if user:
                            return user, None
                        else:
                            # 사용자 정보가 없으면 새로 생성
                            new_user = {"username": username, "chatbots": []}
                            db.users.insert_one(new_user)
                            return new_user, None
                    else:
                        return {"username": username, "chatbots": []}, None
                else:
                    return None, "비밀번호가 잘못되었습니다."
        else:
            return None, "아이디를 찾을 수 없습니다."
    except Exception as e:
        return None, f"로그인 중 오류가 발생했습니다: {str(e)}"

# 비밀번호 변경 함수 수정
def change_password(username, new_password):
    users_data = get_users_data()
    if users_data is None:
        return False, "사용자 데이터를 불러올 수 없어 비밀번호를 변경할 수 없습니다."

    try:
        if not users_data:
            return False, "사용자 데이터가 비어 있습니다."

        # 첫 번째 행의 키(헤더)를 가져옵니다.
        first_row_keys = list(users_data[0].keys())
        # 키를 모두 소문자로 변환하여 비교합니다.
        lower_keys = [key.lower() for key in first_row_keys]

        # '아이디'와 '비밀번호' 키가 있는지 확인합니다.
        if '아이디' in lower_keys:
            id_key = first_row_keys[lower_keys.index('아이디')]
        else:
            return False, "스프레드시트에 '아이디' 열이 없습니다."

        if '비밀번호' in lower_keys:
            password_key = first_row_keys[lower_keys.index('비밀번호')]
        else:
            return False, "스프레드시트에 '비밀번호' 열이 없습니다."

        # 사용자 찾기
        for idx, row in enumerate(users_data):
            if row.get(id_key) == username:
                # 비밀번호 업데이트
                row_number = idx + 2  # 헤더를 고려하여 +2
                col_number = lower_keys.index('비밀번호') + 1  # 인덱스가 0부터 시작하므로 +1
                sheet.update_cell(row_number, col_number, new_password)
                return True, None
        else:
            return False, "사용자를 찾을 수 없습니다."
    except Exception as e:
        return False, f"비밀번호 변경 중 오류가 발생했습니다: {str(e)}"

# 대화 내역 저장 함수
def save_chat_history(chatbot_name, messages):
    if db is not None:
        try:
            chat_history = {
                "chatbot_name": chatbot_name,
                "user": request.json.get('username'),
                "timestamp": datetime.now(),
                "messages": messages
            }
            db.chat_history.insert_one(chat_history)
        except Exception as e:
            print(f"대화 내역 저장 중 오류가 발생했습니다: {str(e)}")

# 오래된 대화 내역 삭제 함수
def delete_old_chat_history():
    if db is not None:
        try:
            one_month_ago = datetime.now() - timedelta(days=30)
            db.chat_history.delete_many({"timestamp": {"$lt": one_month_ago}})
            db.public_chat_history.delete_many({"timestamp": {"$lt": one_month_ago}})
            db.usage_logs.delete_many({"timestamp": {"$lt": one_month_ago}})
        except Exception as e:
            print(f"오래된 대화 내역 삭제 중 오류가 발생했습니다: {str(e)}")

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
            print(f"사용량 기록 중 오류가 발생했습니다: {str(e)}")

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
            print(f"대화 내역 저장 중 오류가 발생했습니다: {str(e)}")

# 챗봇 삭제 함수 수정
def delete_chatbot(chatbot_id, creator):
    if db is not None:
        try:
            result = db.users.update_one(
                {"chatbots._id": ObjectId(chatbot_id), "username": creator},
                {"$pull": {"chatbots": {"_id": ObjectId(chatbot_id)}}}
            )
            if result.modified_count > 0:
                # 관련된 대화 내역도 삭제
                db.chat_history.delete_many({"chatbot_name": chatbot_id})
                db.public_chat_history.delete_many({"chatbot_id": str(chatbot_id)})
                return True, None
            else:
                return False, "챗봇을 찾을 수 없거나 삭제 권한이 없습니다."
        except Exception as e:
            return False, f"챗봇 삭제 중 오류가 발생했습니다: {str(e)}"
    else:
        return False, "데이터베이스 연결이 없어 챗봇을 삭제할 수 없습니다."

# 공유 챗봇 삭제 함수 수정
def delete_shared_chatbot(chatbot_id, username):
    if db is not None:
        try:
            if username == 'admin':
                result = db.shared_chatbots.delete_one({"_id": ObjectId(chatbot_id)})
            else:
                result = db.shared_chatbots.delete_one({"_id": ObjectId(chatbot_id), "creator": username})
            if result.deleted_count > 0:
                return True, None
            else:
                return False, "삭제 권한이 없거나 챗봇을 찾을 수 없습니다."
        except Exception as e:
            return False, f"공유 챗봇 삭제 중 오류가 발생했습니다: {str(e)}"
    else:
        return False, "데이터베이스 연결이 없어 공유 챗봇을 삭제할 수 없습니다."

# 특정 대화 내역 삭제 함수
def delete_specific_chat_history(history_id):
    if db is not None:
        try:
            result = db.chat_history.delete_one({"_id": ObjectId(history_id)})
            if result.deleted_count > 0:
                return True, None
            else:
                return False, "해당 대화 내역을 찾을 수 없습니다."
        except Exception as e:
            return False, f"대화 내역 삭제 중 오류가 발생했습니다: {str(e)}"
    else:
        return False, "데이터베이스 연결이 없어 대화 내역을 삭제할 수 없습니다."

# API 엔드포인트 정의
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user, error = login(username, password)
    if user:
        if user == "change_password":
            return jsonify({"status": "change_password"})
        return jsonify({"status": "success", "user": user})
    else:
        return jsonify({"status": "error", "message": error}), 401

@app.route('/api/change_password', methods=['POST'])
def api_change_password():
    data = request.json
    username = data.get('username')
    new_password = data.get('new_password')
    success, error = change_password(username, new_password)
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": error}), 400

@app.route('/api/create_chatbot', methods=['POST'])
def api_create_chatbot():
    data = request.json
    new_chatbot = {
        "name": data.get('name'),
        "description": data.get('description'),
        "system_prompt": data.get('system_prompt'),
        "welcome_message": data.get('welcome_message'),
        "messages": [{"role": "assistant", "content": data.get('welcome_message')}],
        "creator": data.get('username'),
        "is_shared": data.get('is_shared'),
        "background_color": data.get('background_color'),
        "profile_image_url": data.get('profile_image_url')
    }
    if data.get('is_shared'):
        new_chatbot['category'] = data.get('category')

    if db is not None:
        try:
            if data.get('is_shared'):
                result = db.shared_chatbots.insert_one(new_chatbot)
                new_chatbot['_id'] = str(result.inserted_id)
            else:
                new_chatbot['_id'] = ObjectId()
                db.users.update_one(
                    {"username": data.get('username')},
                    {"$push": {"chatbots": new_chatbot}},
                    upsert=True
                )
            return jsonify({"status": "success", "chatbot": new_chatbot})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "데이터베이스 연결이 없습니다."}), 500

@app.route('/api/update_chatbot', methods=['POST'])
def api_update_chatbot():
    data = request.json
    chatbot_id = data.get('chatbot_id')
    updates = {
        "name": data.get('name'),
        "description": data.get('description'),
        "system_prompt": data.get('system_prompt'),
        "welcome_message": data.get('welcome_message'),
        "background_color": data.get('background_color'),
        "profile_image_url": data.get('profile_image_url')
    }
    if data.get('is_shared'):
        updates['category'] = data.get('category')

    if db is not None:
        try:
            if data.get('is_shared'):
                result = db.shared_chatbots.update_one(
                    {"_id": ObjectId(chatbot_id)},
                    {"$set": updates}
                )
            else:
                result = db.users.update_one(
                    {"username": data.get('username'), "chatbots._id": ObjectId(chatbot_id)},
                    {"$set": {f"chatbots.$.{k}": v for k, v in updates.items()}}
                )
            if result.modified_count > 0:
                return jsonify({"status": "success"})
            else:
                return jsonify({"status": "error", "message": "챗봇을 찾을 수 없거나 변경사항이 없습니다."}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "데이터베이스 연결이 없습니다."}), 500

@app.route('/api/delete_chatbot', methods=['POST'])
def api_delete_chatbot():
    data = request.json
    chatbot_id = data.get('chatbot_id')
    creator = data.get('username')
    success, error = delete_chatbot(chatbot_id, creator)
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": error}), 400

@app.route('/api/delete_shared_chatbot', methods=['POST'])
def api_delete_shared_chatbot():
    data = request.json
    chatbot_id = data.get('chatbot_id')
    username = data.get('username')
    success, error = delete_shared_chatbot(chatbot_id, username)
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": error}), 400

@app.route('/api/generate_response', methods=['POST'])
def api_generate_response():
    data = request.json
    prompt = data.get('prompt')
    chatbot = data.get('chatbot')
    selected_model = data.get('selected_model')

    if is_image_request(prompt):
        image_url = generate_image(prompt)
        if image_url:
            return jsonify({
                "status": "success",
                "response": "요청하신 이미지를 생성했습니다. 이미지를 확인해 주세요.",
                "image_url": image_url
            })
        else:
            return jsonify({
                "status": "error",
                "message": "이미지 생성에 실패했습니다."
            }), 500
    else:
        try:
            start_time = datetime.now()
            if "gpt" in selected_model:
                response = openai_client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "system", "content": chatbot['system_prompt']}] + chatbot['messages'],
                    stream=True
                )
                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        full_response += chunk.choices[0].delta.content
                record_usage(data.get('username'), selected_model, start_time)
            elif "gemini" in selected_model:
                model = genai.GenerativeModel(selected_model)
                response = model.generate_content(chatbot['system_prompt'] + "\n\n" + prompt, stream=True)
                full_response = ""
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                record_usage(data.get('username'), selected_model, start_time)
            elif "claude" in selected_model:
                with anthropic_client.messages.stream(
                    max_tokens=1000,
                    messages=chatbot['messages'],
                    model=selected_model,
                    system=chatbot['system_prompt'],
                ) as stream:
                    full_response = ""
                    for text in stream.text_stream:
                        full_response += text
                record_usage(data.get('username'), selected_model, start_time)
            else:
                return jsonify({"status": "error", "message": "지원되지 않는 모델입니다."}), 400

            return jsonify({"status": "success", "response": full_response})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/save_chat_history', methods=['POST'])
def api_save_chat_history():
    data = request.json
    chatbot_name = data.get('chatbot_name')
    messages = data.get('messages')
    save_chat_history(chatbot_name, messages)
    return jsonify({"status": "success"})

@app.route('/api/save_public_chat_history', methods=['POST'])
def api_save_public_chat_history():
    data = request.json
    chatbot_id = data.get('chatbot_id')
    user_name = data.get('user_name')
    messages = data.get('messages')
    save_public_chat_history(chatbot_id, user_name, messages)
    return jsonify({"status": "success"})

@app.route('/api/get_chat_history', methods=['GET'])
def api_get_chat_history():
    username = request.args.get('username')
    chatbot_name = request.args.get('chatbot_name')
    if db is not None:
        chat_histories = list(db.chat_history.find({
            "chatbot_name": chatbot_name,
            "user": username
        }).sort("timestamp", -1))
        for history in chat_histories:
            history['_id'] = str(history['_id'])
            history['timestamp'] = history['timestamp'].isoformat()
        return jsonify({"status": "success", "chat_histories": chat_histories})
    else:
        return jsonify({"status": "error", "message": "데이터베이스 연결이 없습니다."}), 500

@app.route('/api/get_public_chat_history', methods=['GET'])
def api_get_public_chat_history():
    chatbot_id = request.args.get('chatbot_id')
    if db is not None:
        chat_histories = list(db.public_chat_history.find({
            "chatbot_id": chatbot_id
        }).sort("timestamp", -1))
        for history in chat_histories:
            history['_id'] = str(history['_id'])
            history['timestamp'] = history['timestamp'].isoformat()
        return jsonify({"status": "success", "chat_histories": chat_histories})
    else:
        return jsonify({"status": "error", "message": "데이터베이스 연결이 없습니다."}), 500

@app.route('/api/delete_chat_history', methods=['POST'])
def api_delete_chat_history():
    data = request.json
    history_id = data.get('history_id')
    success, error = delete_specific_chat_history(history_id)
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": error}), 400

@app.route('/api/get_usage_data', methods=['GET'])
def api_get_usage_data():
    if db is not None:
        usage_logs = list(db.usage_logs.find())
        for log in usage_logs:
            log['_id'] = str(log['_id'])
            log['timestamp'] = log['timestamp'].isoformat()
        return jsonify({"status": "success", "usage_logs": usage_logs})
    else:
        return jsonify({"status": "error", "message": "데이터베이스 연결이 없습니다."}), 500

# 주기적으로 오래된 대화 내역 삭제
@app.before_request
def before_request():
    delete_old_chat_history()

if __name__ == "__main__":
    app.run(debug=True)
