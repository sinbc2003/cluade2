import React, { useState } from 'react';
import { useHistory } from 'react-router-dom';
import axios from 'axios';

function CreateChatbot({ user }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('역할 : 당신의 역할은 {}이다.\n규칙 : 다음 규칙을 따라 사용자에게 답변한다.\n- {내용1}\n- {내용2}\n- {내용3}');
  const [welcomeMessage, setWelcomeMessage] = useState('안녕하세요! 무엇을 도와드릴까요?');
  const [isShared, setIsShared] = useState(false);
  const [backgroundColor, setBackgroundColor] = useState('#FFFFFF');
  const [category, setCategory] = useState('');
  const [profileImageUrl, setProfileImageUrl] = useState('https://via.placeholder.com/100');
  const [error, setError] = useState('');
  const history = useHistory();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('/api/create_chatbot', {
        name,
        description,
        system_prompt: systemPrompt,
        welcome_message: welcomeMessage,
        is_shared: isShared,
        background_color: backgroundColor,
        category: isShared ? category : null,
        profile_image_url: profileImageUrl,
        username: user.username
      });

      if (response.data.status === 'success') {
        history.push(isShared ? '/shared-chatbots' : '/available-chatbots');
      } else {
        setError('챗봇 생성에 실패했습니다. 다시 시도해주세요.');
      }
    } catch (error) {
      console.error('Error creating chatbot:', error);
      setError('챗봇 생성 중 오류가 발생했습니다.');
    }
  };

  const generateProfileImage = async () => {
    try {
      const response = await axios.post('/api/generate_image', {
        prompt: `Create a profile image for a chatbot named '${name}'. Description: ${description}`
      });
      if (response.data.status === 'success') {
        setProfileImageUrl(response.data.image_url);
      } else {
        setError('프로필 이미지 생성에 실패했습니다.');
      }
    } catch (error) {
      console.error('Error generating profile image:', error);
      setError('프로필 이미지 생성 중 오류가 발생했습니다.');
    }
  };

  return (
    <div className="create-chatbot-container">
      <h2>새 챗봇 만들기</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name">챗봇 이름:</label>
          <input
            type="text"
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="description">챗봇 소개:</label>
          <input
            type="text"
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="systemPrompt">시스템 프롬프트:</label>
          <textarea
            id="systemPrompt"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="welcomeMessage">웰컴 메시지:</label>
          <input
            type="text"
            id="welcomeMessage"
            value={welcomeMessage}
            onChange={(e) => setWelcomeMessage(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="isShared">다른 교사와 공유하기:</label>
          <input
            type="checkbox"
            id="isShared"
            checked={isShared}
            onChange={(e) => setIsShared(e.target.checked)}
          />
        </div>
        {isShared && (
          <div>
            <label htmlFor="category">챗봇 범주:</label>
            <input
              type="text"
              id="category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              required
            />
          </div>
        )}
        <div>
          <label htmlFor="backgroundColor">챗봇 카드 배경색:</label>
          <input
            type="color"
            id="backgroundColor"
            value={backgroundColor}
            onChange={(e) => setBackgroundColor(e.target.value)}
          />
        </div>
        <div>
          <label>프로필 이미지:</label>
          <img src={profileImageUrl} alt="프로필 이미지" width="100" />
          <button type="button" onClick={generateProfileImage}>프로필 이미지 생성</button>
        </div>
        {error && <p className="error-message">{error}</p>}
        <button type="submit">챗봇 생성</button>
      </form>
    </div>
  );
}

export default CreateChatbot;
