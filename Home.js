import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

function Home({ user, onLogout }) {
  const [selectedModel, setSelectedModel] = useState('gpt-4o');
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const result = await axios.post('/api/generate_response', {
        prompt,
        selected_model: selectedModel,
        username: user.username
      });
      setResponse(result.data.response);
    } catch (error) {
      console.error('Error generating response:', error);
      setResponse('오류가 발생했습니다. 다시 시도해주세요.');
    }
    setIsLoading(false);
  };

  return (
    <div className="home-container">
      <h1>Welcome, {user.username}!</h1>
      <nav>
        <ul>
          <li><Link to="/create-chatbot">새 챗봇 만들기</Link></li>
          <li><Link to="/available-chatbots">나만 사용 가능한 챗봇</Link></li>
          <li><Link to="/shared-chatbots">수원외국어고등학교 공유 챗봇</Link></li>
          <li><Link to="/chat-history">대화 내역 확인</Link></li>
          {user.username === 'admin' && <li><Link to="/usage-data">사용량 데이터</Link></li>}
        </ul>
      </nav>
      <button onClick={onLogout}>로그아웃</button>

      <div className="default-bot">
        <h2>Default 봇</h2>
        <form onSubmit={handleSubmit}>
          <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4o-mini">GPT-4o-mini</option>
            <option value="gemini-pro">Gemini Pro</option>
            <option value="gemini-1.5-pro-latest">Gemini 1.5 Pro Latest</option>
            <option value="claude-3-5-sonnet-20240620">Claude 3.5 Sonnet</option>
            <option value="claude-3-opus-20240229">Claude 3 Opus</option>
            <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
          </select>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="무엇을 도와드릴까요?"
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? '생성 중...' : '전송'}
          </button>
        </form>
        {response && (
          <div className="response">
            <h3>응답:</h3>
            <p>{response}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Home;
