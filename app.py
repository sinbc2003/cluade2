import streamlit as st
from utils import (
    load_chatbots, 
    create_chatbot, 
    get_chatbot_response, 
    check_password, 
    process_latex, 
    update_chatbot, 
    delete_chatbot, 
    get_chatbot_by_id, 
    save_conversation, 
    get_all_conversations,
    generate_image,
    generate_profile_image,
    optimize_image,
    load_chatbots_paginated,
    save_generated_content,
    get_conversations_summary,
    get_conversation_details,
    get_gemini_response,
    get_claude_response
)
import base64
from io import BytesIO
from bson import ObjectId
import re

def render_latex(text):
    return st.markdown(text, unsafe_allow_html=True)

def is_image_request(text):
    image_patterns = [
        r'이미지.*[생성만들어]',
        r'사진.*[찍어줘만들어]',
        r'그림.*[그려줘만들어]',
        r'[생성만들어].*이미지',
        r'[그려줘만들어].*그림',
        r'[시각화시각적].*표현',
        r'비주얼.*[만들어생성]'
    ]
    return any(re.search(pattern, text) for pattern in image_patterns)

def chat_page(chatbot):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"{chatbot['name']}과의 대화")
    with col2:
        if 'profile_image' in chatbot and chatbot['profile_image']:
            st.image(chatbot['profile_image'], width=100)
    
    st.write(chatbot['description'])
    
    messages_key = f"messages_{chatbot['id']}"
    if messages_key not in st.session_state:
        st.session_state[messages_key] = []
        if 'welcome_message' in chatbot and chatbot['welcome_message']:
            st.session_state[messages_key].append({"role": "assistant", "type": "text", "content": chatbot['welcome_message']})

    model = st.selectbox("모델 선택", ["gpt-4o", "gpt-4o-mini", "gemini-pro", "gemini-1.5-flash", "claude-3-5-sonnet-20240620"])

    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state[messages_key]:
            with st.chat_message(message["role"]):
                if message["type"] == "text":
                    render_latex(message["content"])
                elif message["type"] == "image":
                    st.image(message["content"])

    if prompt := st.chat_input("메시지를 입력하세요"):
        st.session_state[messages_key].append({"role": "user", "type": "text", "content": prompt})
        with st.chat_message("user"):
            render_latex(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            conversation_history = [
                {"role": "system", "content": chatbot['system_prompt']},
                {"role": "system", "content": "You are an AI assistant capable of generating images. When a user asks for an image, respond that you will generate it and then proceed with the image generation."}
            ] + [msg for msg in st.session_state[messages_key] if msg["type"] == "text"]
            
            if is_image_request(prompt):
                full_response = "이미지를 생성하겠습니다. 잠시만 기다려 주세요."
                message_placeholder.markdown(full_response)
                
                with st.spinner("이미지 생성 중..."):
                    image_url = generate_image(prompt)
                    if image_url:
                        st.image(image_url)
                        st.session_state[messages_key].append({"role": "assistant", "type": "image", "content": image_url})
                        full_response += "\n\n요청하신 이미지를 생성했습니다. 위의 이미지를 확인해 주세요."
                    else:
                        full_response += "\n\n죄송합니다. 이미지 생성 중 오류가 발생했습니다."
            else:
                if model.startswith("gpt"):
                    for response in get_chatbot_response(conversation_history + [{"role": "user", "content": prompt}], model):
                        if response.choices[0].delta.content is not None:
                            full_response += response.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                elif model.startswith("gemini"):
                    full_response = get_gemini_response(prompt, model)
                    message_placeholder.markdown(full_response)
                elif model.startswith("claude"):
                    for text in get_claude_response(conversation_history + [{"role": "user", "content": prompt}], model):
                        full_response += text
                        message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)

        st.session_state[messages_key].append({"role": "assistant", "type": "text", "content": full_response})

        conversation_id = save_conversation(st.session_state.username, chatbot['id'], st.session_state[messages_key])
        if conversation_id is None:
            st.warning("대화 저장에 실패했습니다. 관리자에게 문의하세요.")

        if is_image_request(prompt):
            save_generated_content(conversation_id, "image", image_url)

        st.rerun()

def admin_page():
    st.title("관리자 페이지")
    
    # 대화 내역 요약
    st.subheader("대화 내역")
    page = st.number_input("페이지", min_value=1, value=1)
    per_page = 10
    conversations_summary = get_conversations_summary(page, per_page)
    
    for conv in conversations_summary:
        with st.expander(f"사용자: {conv['username']}, 챗봇: {conv['chatbot_name']}, 시간: {conv['timestamp']}"):
            st.write(f"메시지 수: {conv['message_count']}")
            if st.button("상세 보기", key=f"view_{conv['_id']}"):
                details = get_conversation_details(conv['_id'])
                st.json(details)

    # 챗봇 관리
    st.title("챗봇 관리")
    chatbot_page = st.number_input("챗봇 페이지", min_value=1, value=1)
    chatbots, total_pages = load_chatbots_paginated(chatbot_page)
    
    for chatbot in chatbots:
        st.subheader(chatbot.get('name', 'Unnamed Chatbot'))
        st.write(chatbot.get('description', 'No description available'))
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button(f"{chatbot.get('name', 'Unnamed')} 수정", key=f"edit_{chatbot.get('id', 'unknown')}"):
                st.session_state.current_page = "edit_chatbot"
                st.session_state.edit_chatbot_id = chatbot.get('id')
                st.rerun()
        with col2:
            if st.button(f"{chatbot.get('name', 'Unnamed')} 삭제", key=f"delete_{chatbot.get('id', 'unknown')}"):
                if 'id' in chatbot:
                    if delete_chatbot(ObjectId(chatbot['id'])):
                        st.success(f"챗봇 '{chatbot.get('name', 'Unnamed')}'이(가) 삭제되었습니다.")
                        st.rerun()
                    else:
                        st.error("챗봇 삭제 중 오류가 발생했습니다.")
                else:
                    st.error("챗봇 ID를 찾을 수 없습니다.")
        with col3:
            if st.button(f"{chatbot.get('name', 'Unnamed')} 지침 수정", key=f"edit_instructions_{chatbot.get('id', 'unknown')}"):
                st.session_state.current_page = "edit_instructions"
                st.session_state.edit_chatbot_id = chatbot.get('id')
                st.rerun()
    
    st.write(f"페이지 {chatbot_page}/{total_pages}")
    if chatbot_page < total_pages:
        if st.button("다음 페이지"):
            st.session_state.chatbot_page = chatbot_page + 1
            st.rerun()
    if chatbot_page > 1:
        if st.button("이전 페이지"):
            st.session_state.chatbot_page = chatbot_page - 1
            st.rerun()

def edit_chatbot_page(chatbot_id):
    chatbot = get_chatbot_by_id(ObjectId(chatbot_id))
    st.title(f"{chatbot['name']} 수정")
    new_name = st.text_input("챗봇 이름:", value=chatbot['name'])
    new_description = st.text_area("챗봇 소개:", value=chatbot['description'])
    new_system_prompt = st.text_area("시스템 프롬프트:", value=chatbot['system_prompt'])
    new_welcome_message = st.text_area("웰컴 메시지:", value=chatbot.get('welcome_message', ''))
    new_background_color = st.color_picker("카드 배경색:", value=chatbot.get('background_color', '#F5E6D3'))
    
    if st.button("프로필 이미지 재생성"):
        with st.spinner("프로필 이미지 생성 중..."):
            try:
                profile_image = generate_profile_image(new_name, new_description)
                if profile_image:
                    optimized_image = optimize_image(profile_image)
                    chatbot['profile_image'] = optimized_image
                    st.image(optimized_image)
                    st.success("프로필 이미지가 재생성되었습니다.")
                else:
                    st.error("프로필 이미지 생성에 실패했습니다.")
            except Exception as e:
                st.error(f"프로필 이미지 생성 중 오류가 발생했습니다: {str(e)}")
    
    if st.button("변경 사항 저장"):
        updated_chatbot = update_chatbot(ObjectId(chatbot_id), new_name, new_description, new_system_prompt, chatbot.get('profile_image'), new_welcome_message, new_background_color)
        if updated_chatbot:
            st.success(f"챗봇 '{updated_chatbot['name']}'의 정보가 업데이트되었습니다.")
            st.session_state.current_page = "admin"
            st.rerun()
        else:
            st.error("챗봇 정보 업데이트 중 오류가 발생했습니다.")

def edit_instructions_page(chatbot_id):
    chatbot = get_chatbot_by_id(ObjectId(chatbot_id))
    st.title(f"{chatbot['name']} 지침 수정")
    new_system_prompt = st.text_area("시스템 프롬프트:", value=chatbot['system_prompt'], height=300)
    
    if st.button("변경 사항 저장"):
        updated_chatbot = update_chatbot(ObjectId(chatbot_id), chatbot['name'], chatbot['description'], new_system_prompt, chatbot.get('profile_image'), chatbot.get('welcome_message', ''), chatbot.get('background_color', '#F5E6D3'))
        if updated_chatbot:
            st.success(f"챗봇 '{updated_chatbot['name']}'의 지침이 업데이트되었습니다.")
            st.session_state.current_page = "home"
            st.rerun()
        else:
            st.error("챗봇 지침 업데이트 중 오류가 발생했습니다.")

def create_chatbot_page():
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("새로운 챗봇 만들기")
        name = st.text_input("챗봇 이름:")
        description = st.text_input("챗봇 소개:")
        system_prompt = st.text_area("시스템 프롬프트:", height=300)
        welcome_message = st.text_input("웰컴 메시지:")
        background_color = st.color_picker("카드 배경색:", value='#F5E6D3')
        
        if st.button("프로필 이미지 생성"):
            with st.spinner("프로필 이미지 생성 중..."):
                try:
                    profile_image = generate_profile_image(name, description)
                    if profile_image:
                        optimized_image = optimize_image(profile_image)
                        st.session_state.new_profile_image = optimized_image
                        st.image(optimized_image)
                        st.success("프로필 이미지가 생성되었습니다.")
                    else:
                        st.error("프로필 이미지 생성에 실패했습니다.")
                except Exception as e:
                    st.error(f"프로필 이미지 생성 중 오류가 발생했습니다: {str(e)}")
        
        if st.button("챗봇 생성"):
            new_chatbot = create_chatbot(name, description, system_prompt, st.session_state.get('new_profile_image'), welcome_message, background_color)
            if new_chatbot:
                st.success(f"챗봇 '{new_chatbot['name']}'이(가) 성공적으로 생성되었습니다!")
                st.session_state.current_page = "chat"
                st.session_state.current_chatbot_id = new_chatbot['id']
                if 'new_profile_image' in st.session_state:
                    del st.session_state.new_profile_image
                st.rerun()
            else:
                st.error("챗봇 생성 중 오류가 발생했습니다.")

def display_available_chatbots():
    st.title("사용 가능한 챗봇")

    # Initialize page state if it doesn't exist
    if 'page' not in st.session_state:
        st.session_state.page = 1
    
    # 페이지네이션된 챗봇 로드
    chatbots, total_pages = load_chatbots_paginated(st.session_state.page)
    
    # 페이지 선택 드롭다운
    page = st.selectbox("페이지 선택", range(1, total_pages + 1), index=st.session_state.page - 1, key="page_select")
    if page != st.session_state.page:
        st.session_state.page = page
        st.rerun()
    
    # 2열로 챗봇 카드 표시
    cols = st.columns(2)
    for idx, chatbot in enumerate(chatbots):
        with cols[idx % 2]:
            with st.container():
                st.markdown(f"""
                <div class="chatbot-card" style="background-color: {chatbot.get('background_color', '#F5E6D3')};">
                    <div style="display: flex;">
                        <div style="flex: 0 0 100px;">
                            <img src="{chatbot.get('profile_image', 'https://via.placeholder.com/100')}" class="chatbot-profile">
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
                    if st.button("대화하기", key=f"chat_{chatbot.get('id', 'unknown')}_{st.session_state.page}_{idx}"):
                        st.session_state.current_page = "chat"
                        st.session_state.current_chatbot_id = chatbot['id']
                        st.rerun()
                with col2:
                    if st.button("지침 수정", key=f"edit_instructions_{chatbot.get('id', 'unknown')}_{st.session_state.page}_{idx}"):
                        st.session_state.current_page = "edit_instructions"
                        st.session_state.edit_chatbot_id = chatbot['id']
                        st.rerun()

def main():
    st.set_page_config(page_title="챗봇 플랫폼", page_icon=":robot_face:", layout="wide")
    
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
    .stSelectbox {
        margin-bottom: 20px;
    }
    #admin-access {
        position: fixed;
        left: 20px;
        bottom: 20px;
        z-index: 1000;
    }
    .chatbot-card {
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        height: 100%;
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
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
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.5/MathJax.js?config=TeX-MML-AM_CHTML"></script>
    <script>
    MathJax.Hub.Config({
        tex2jax: {
            inlineMath: [['$','$'], ['\\(','\\)']],
            processEscapes: true
        },
        "HTML-CSS": {
            linebreaks: { automatic: true }
        },
        SVG: {
            linebreaks: { automatic: true }
        }
    });
    </script>
    """, unsafe_allow_html=True)

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "home"
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False

    st.markdown('<div id="admin-access">⚙️</div>', unsafe_allow_html=True)
    if st.sidebar.checkbox("관리자 로그인", key="admin_login"):
        admin_password = st.sidebar.text_input("관리자 비밀번호", type="password")
        if st.sidebar.button("확인"):
            if check_password(admin_password):
                st.session_state.is_admin = True
                st.session_state.current_page = "admin"
                st.rerun()
            else:
                st.sidebar.error("관리자 비밀번호가 올바르지 않습니다.")

    if not st.session_state.authenticated:
        st.title("로그인")
        username = st.text_input("사용자 이름")
        password = st.text_input("비밀번호", type="password")
        if st.button("로그인") or (password and st.session_state.get('password_entered', False)):
            st.session_state.password_entered = True
            if check_password(password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.current_page = "home"
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    else:
        with st.sidebar:
            st.title("챗봇 플랫폼")
            
            if st.button("홈"):
                st.session_state.current_page = "home"
                st.rerun()
            
            if st.button("사용 가능한 챗봇"):
                st.session_state.current_page = "available_chatbots"
                st.rerun()
            
            if st.button("새 챗봇 만들기"):
                st.session_state.current_page = "create_chatbot"
                st.rerun()

            if st.session_state.current_page == "chat" or st.session_state.current_page == "home":
                if st.button("대화 내역 초기화"):
                    messages_key = f"messages_{st.session_state.get('current_chatbot_id', 'default')}"
                    st.session_state[messages_key] = []
                    st.success("대화 내역이 초기화되었습니다.")
                    st.rerun()

            if st.button("로그아웃", key="logout"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        if st.session_state.current_page == "home":
            chat_page({"name": "기본 모델", "id": "default", "description": "기본 AI 모델과 대화하세요.", "system_prompt": "You are a helpful assistant."})
        
        elif st.session_state.current_page == "chat":
            chatbot = get_chatbot_by_id(ObjectId(st.session_state.current_chatbot_id))
            if chatbot:
                chat_page(chatbot)
            else:
                st.error("챗봇을 찾을 수 없습니다.")

        elif st.session_state.current_page == "admin" and st.session_state.is_admin:
            admin_page()
        elif st.session_state.current_page == "edit_chatbot" and st.session_state.is_admin:
            edit_chatbot_page(st.session_state.edit_chatbot_id)
        elif st.session_state.current_page == "edit_instructions":
            edit_instructions_page(st.session_state.edit_chatbot_id)
        elif st.session_state.current_page == "available_chatbots":
            display_available_chatbots()
        elif st.session_state.current_page == "create_chatbot":
            create_chatbot_page()

if __name__ == "__main__":
    main()
