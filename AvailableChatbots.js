import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

function AvailableChatbots({ user }) {
  const [chatbots, setChatbots] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchChatbots();
  }, []);

  const fetchChatbots = async () => {
    try {
      const response = await axios.get(`/api/available_chatbots?username=${user.username}`);
      if (response.data.status === 'success') {
        setChatbots(response.data.chatbots);
      } else {
        setError('챗봇 목록을 불러오는데 실패했습니다.');
      }
    } catch (error) {
      console.error('Error fetching chatbots:', error);
      setError('챗봇 목록을 불러오는 중 오류가 발생했습니다.');
    }
  };

  const deleteChatbot = async (chatbotId) => {
    if (window.confirm('정말로 이 챗봇을 삭제하시겠습니까?')) {
      try {
        const response = await axios.post('/api/delete_chatbot', {
          chatbot_id: chatbotId,
          username: user.username
        });
        if (response.data.status === 'success') {
          fetchChatbots();  // 목록 새로고침
        } else {
          setError('챗봇 삭제에 실패했습니다.');
        }
      } catch (error) {
        console.error('Error deleting chatbot:', error);
        setError('챗봇 삭제 중 오류가 발생했습니다.');
      }
    }
  };

  const generateShareableUrl = (chatbotId, model) => {
    const baseUrl = window.location.origin;
    return `${baseUrl}/public-chatbot/${chatbotId}?model=${encodeURIComponent(model)}`;
  };

  return (
    <div className="available-chatbots-container">
      <h2>나만 사용 가능한 챗봇</h2>
      {error && <p className="error-message">{error}</p>}
      {chatbots.length === 0 ? (
        <p>아직 만든 챗봇이 없습니다. '새 챗봇 만들기'에서 첫 번째 챗봇을 만들어보세요!</p>
      ) : (
        <div className="chatbot-grid">
          {chatbots.map((chatbot) => (
            <div key={chatbot._id} className="chatbot-card" style={{backgroundColor: chatbot.background_color}}>
              <img src={chatbot.profile_image_url} alt="프로필 이미지" />
              <h3>{chatbot.name}</h3>
              <p>{chatbot.description}</p>
              <div className="chatbot-actions">
                <Link to={`/chatbot/${chatbot._id}`}>사용하기</Link>
                <Link to={`/edit-chatbot/${chatbot._id}`}>수정하기</Link>
                <button onClick={() => deleteChatbot(chatbot._id)}>삭제하기</button>
              </div>
              <div className="share-url">
                <select onChange={(e) => {
                  const url = generateShareableUrl(chatbot._id, e.target.value);
                  navigator.clipboard.writeText(url);
                  alert('URL이 클립보드에 복사되었습니다!');
                }}>
                  <option value="">모델 선택</option>
                  {["gpt-4o", "gpt-4o-mini", "gemini-pro", "gemini-1.5-pro-latest", "claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307"].map((model) => (
                    <option key={model} value={model}>{model}</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AvailableChatbots;
