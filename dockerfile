# 베이스 이미지로 Python 3.9 사용
FROM python:3.9-slim

# Node.js 설치
RUN apt-get update && apt-get install -y nodejs npm

# 작업 디렉토리 설정
WORKDIR /app

# 백엔드 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프론트엔드 파일 복사 및 빌드
COPY frontend /app/frontend
WORKDIR /app/frontend
RUN npm install
RUN npm run build

# 백엔드 파일 복사
WORKDIR /app
COPY app.py .

# 환경 변수 설정
ENV PORT 8080

# 포트 노출
EXPOSE 8080

# 앱 실행
CMD ["python", "app.py"]
