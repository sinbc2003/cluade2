# 베이스 이미지로 Python 3.9 사용
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 시스템 패키지 설치
RUN apt-get update && apt-get install -y build-essential

# 필요한 파일 복사
COPY requirements.txt .
COPY app.py .

# 종속성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 환경 변수 설정
ENV PORT 8080

# 앱 실행
CMD ["streamlit", "run", "app.py", "--server.port=${PORT}", "--server.address=0.0.0.0"]
