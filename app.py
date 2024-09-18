import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Route, Switch, Redirect, Link, useParams, useHistory } from 'react-router-dom';
import axios from 'axios';

// 메인 App 컴포넌트
function App() {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setIsLoading(false);
  }, []);

  const login = async (username, password) => {
    try {
      const response = await axios.post('/api/login', { username, password });
      if (response.data.status === 'success') {
        setUser(response.data.user);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        return true;
      } else if (response.data.status === 'change_password') {
        return 'change_password';
      }
    } catch (error) {
      console.error('Login error:', error);
      return false;
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('user');
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <Router>
      <Switch>
        <Route exact path="/" render={() => (
          user ? <Redirect to="/home" /> : <Login onLogin={login} />
        )} />
        <Route path="/change-password" component={ChangePassword} />
        <Route path="/home" render={() => (
          user ? <Home user={user} onLogout={logout} /> : <Redirect to="/" />
        )} />
        <Route path="/create-chatbot" render={() => (
          user ? <CreateChatbot user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/available-chatbots" render={() => (
          user ? <AvailableChatbots user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/shared-chatbots" render={() => (
          user ? <SharedChatbots user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/chatbot/:id" render={(props) => (
          user ? <ChatbotPage {...props} user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/shared-chatbot/:id" render={(props) => (
          user ? <SharedChatbotPage {...props} user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/chat-history" render={() => (
          user ? <ChatHistory user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/edit-chatbot/:id" render={(props) => (
          user ? <EditChatbot {...props} user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/edit-shared-chatbot/:id" render={(props) => (
          user ? <EditSharedChatbot {...props} user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/public-chatbot/:id" component={PublicChatbotPage} />
        <Route path="/view-public-chat-history/:id" render={(props) => (
          user ? <ViewPublicChatHistory {...props} user={user} /> : <Redirect to="/" />
        )} />
        <Route path="/usage-data" render={() => (
          user && user.username === 'admin' ? <UsageData /> : <Redirect to="/" />
        )} />
      </Switch>
    </Router>
  );
}

// Login 컴포넌트
function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const history = useHistory();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const result = await onLogin(username, password);
      if (result === true) {
        history.push('/home');
      } else if (result === 'change_password') {
        history.push('/change-password', { username });
      } else {
        setError('로그인에 실패했습니다. 아이디와 비밀번호를 확인해주세요.');
      }
    } catch (error) {
      setError('로그인 중 오류가 발생했습니다. 다시 시도해주세요.');
    }
  };

  return (
    <div className="login-container">
      <h2>로그인</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="username">아이디:</label>
          <input
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password">비밀번호:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <p className="error-message">{error}</p>}
        <button type="submit">로그인</button>
      </form>
    </div>
  );
}

// ChangePassword 컴포넌트
function ChangePassword() {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const history = useHistory();
  const { username } = history.location.state || {};

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError('새 비밀번호가 일치하지 않습니다.');
      return;
    }
    try {
      const response = await axios.post('/api/change_password', { username, new_password: newPassword });
      if (response.data.status === 'success') {
        setSuccess(true);
        setTimeout(() => history.push('/'), 3000);
      } else {
        setError('비밀번호 변경에 실패했습니다.');
      }
    } catch (error) {
      setError('비밀번호 변경 중 오류가 발생했습니다.');
    }
  };

  return (
    <div className="change-password-container">
      <h2>비밀번호 변경</h2>
      {success ? (
        <p>비밀번호가 성공적으로 변경되었습니다. 로그인 페이지로 이동합니다...</p>
      ) : (
        <form onSubmit={handleSubmit}>
          <div>
            <label htmlFor="newPassword">새 비밀번호:</label>
            <input
              type="password"
              id="newPassword"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor="confirmPassword">새 비밀번호 확인:</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="error-message">{error}</p>}
          <button type="submit">비밀번호 변경</button>
        </form>
      )}
    </div>
  );
}

// Home 컴포넌트
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

// CreateChatbot 컴포넌트
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

// AvailableChatbots 컴포넌트
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

// SharedChatbots 컴포넌트
function SharedChatbots({ user }) {
  const [chatbots, setChatbots] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSharedChatbots();
  }, []);

  const fetchSharedChatbots = async () => {
    try {
      const response = await axios.get('/api/shared_chatbots');
      if (response.data.status === 'success') {
        setChatbots(response.data.chatbots);
      } else {
        setError('공유 챗봇 목록을 불러오는데 실패했습니다.');
      }
    } catch (error) {
      console.error('Error fetching shared chatbots:', error);
      setError('공유 챗봇 목록을 불러오는 중 오류가 발생했습니다.');
    }
  };

  const deleteSharedChatbot = async (chatbotId) => {
    if (window.confirm('정말로 이 공유 챗봇을 삭제하시겠습니까?')) {
      try {
        const response = await axios.post('/api/delete_shared_chatbot', {
          chatbot_id: chatbotId,
          username: user.username
        });
        if (response.data.status === 'success') {
          fetchSharedChatbots();  // 목록 새로고침
        } else {
          setError('공유 챗봇 삭제에 실패했습니다.');
        }
      } catch (error) {
        console.error('Error deleting shared chatbot:', error);
        setError('공유 챗봇 삭제 중 오류가 발생했습니다.');
      }
    }
  };

  return (
    <div className="shared-chatbots-container">
      <h2>수원외국어고등학교 공유 챗봇</h2>
      {error && <p className="error-message">{error}</p>}
      {chatbots.length === 0 ? (
        <p>현재 공유된 챗봇이 없습니다.</p>
      ) : (
        <div className="chatbot-grid">
          {chatbots.map((chatbot) => (
            <div key={chatbot._id} className="chatbot-card" style={{backgroundColor: chatbot.background_color}}>
              <img src={chatbot.profile_image_url} alt="프로필 이미지" />
              <h3>{chatbot.name}</h3>
              <p>{chatbot.description}</p>
              <p>작성자: {chatbot.creator}</p>
              <p>범주: {chatbot.category}</p>
              <div className="chatbot-actions">
                <Link to={`/shared-chatbot/${chatbot._id}`}>사용하기</Link>
                {(user.username === chatbot.creator || user.username === 'admin') && (
                  <>
                    <Link to={`/edit-shared-chatbot/${chatbot._id}`}>수정하기</Link>
                    <button onClick={() => deleteSharedChatbot(chatbot._id)}>삭제하기</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ChatbotPage 컴포넌트
function ChatbotPage({ user }) {
  const { id } = useParams();
  const [chatbot, setChatbot] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('gpt-4o');
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchChatbot();
  }, [id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchChatbot = async () => {
    try {
      const response = await axios.get(`/api/chatbot/${id}?username=${user.username}`);
      if (response.data.status === 'success') {
        setChatbot(response.data.chatbot);
        setMessages(response.data.chatbot.messages || []);
      } else {
        setError('챗봇 정보를 불러오는데 실패했습니다.');
      }
    } catch (error) {
      console.error('Error fetching chatbot:', error);
      setError('챗봇 정보를 불러오는 중 오류가 발생했습니다.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const newMessage = { role: 'user', content: input };
    setMessages([...messages, newMessage]);
    setInput('');

    try {
      const response = await axios.post('/api/generate_response', {
        prompt: input,
        chatbot: chatbot,
        selected_model: selectedModel,
        username: user.username
      });

      if (response.data.status === 'success') {
        const botResponse = { role: 'assistant', content: response.data.response };
        if (response.data.image_url) {
          botResponse.image_url = response.data.image_url;
        }
        setMessages(prevMessages => [...prevMessages, botResponse]);
      } else {
        setError('응답 생성에 실패했습니다.');
      }
    } catch (error) {
      console.error('Error generating response:', error);
      setError('응답 생성 중 오류가 발생했습니다.');
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const resetChat = async () => {
    if (window.confirm('정말로 대화 내역을 초기화하시겠습니까?')) {
      try {
        const response = await axios.post('/api/reset_chat', {
          chatbot_id: id,
          username: user.username
        });
        if (response.data.status === 'success') {
          setMessages([{ role: 'assistant', content: chatbot.welcome_message }]);
        } else {
          setError('대화 내역 초기화에 실패했습니다.');
        }
      } catch (error) {
        console.error('Error resetting chat:', error);
        setError('대화 내역 초기화 중 오류가 발생했습니다.');
      }
    }
  };

  if (!chatbot) {
    return <div>Loading...</div>;
  }

  return (
    <div className="chatbot-page">
      <div className="chatbot-header">
        <img src={chatbot.profile_image_url} alt="프로필 이미지" />
        <h2>{chatbot.name}</h2>
        {(user.username === chatbot.creator || user.username === 'admin') && (
          <Link to={`/edit-chatbot/${id}`} className="edit-button">수정</Link>
        )}
      </div>
      <div className="chat-container">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            {message.image_url && <img src={message.image_url} alt="생성된 이미지" />}
            <p>{message.content}</p>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} className="input-form">
        <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
          <option value="gpt-4o">GPT-4o</option>
          <option value="gpt-4o-mini">GPT-4o-mini</option>
          <option value="gemini-pro">Gemini Pro</option>
          <option value="gemini-1.5-pro-latest">Gemini 1.5Pro Latest</option>
          <option value="claude-3-5-sonnet-20240620">Claude 3.5 Sonnet</option>
          <option value="claude-3-opus-20240229">Claude 3 Opus</option>
          <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
        </select>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="메시지를 입력하세요..."
        />
        <button type="submit">전송</button>
      </form>
      <button onClick={resetChat} className="reset-button">대화 내역 초기화</button>
      {error && <p className="error-message">{error}</p>}
    </div>
  );
}

// EditChatbot 컴포넌트
function EditChatbot({ user }) {
  const { id } = useParams();
  const history = useHistory();
  const [chatbot, setChatbot] = useState(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [welcomeMessage, setWelcomeMessage] = useState('');
  const [backgroundColor, setBackgroundColor] = useState('#FFFFFF');
  const [profileImageUrl, setProfileImageUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetchChatbot();
  }, [id]);

  const fetchChatbot = async () => {
    try {
      const response = await axios.get(`/api/chatbot/${id}?username=${user.username}`);
      if (response.data.status === 'success') {
        const fetchedChatbot = response.data.chatbot;
        setChatbot(fetchedChatbot);
        setName(fetchedChatbot.name);
        setDescription(fetchedChatbot.description);
        setSystemPrompt(fetchedChatbot.system_prompt);
        setWelcomeMessage(fetchedChatbot.welcome_message);
        setBackgroundColor(fetchedChatbot.background_color);
        setProfileImageUrl(fetchedChatbot.profile_image_url);
      } else {
        setError('챗봇 정보를 불러오는데 실패했습니다.');
      }
    } catch (error) {
      console.error('Error fetching chatbot:', error);
      setError('챗봇 정보를 불러오는 중 오류가 발생했습니다.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('/api/update_chatbot', {
        chatbot_id: id,
        name,
        description,
        system_prompt: systemPrompt,
        welcome_message: welcomeMessage,
        background_color: backgroundColor,
        profile_image_url: profileImageUrl,
        username: user.username
      });

      if (response.data.status === 'success') {
        history.push(`/chatbot/${id}`);
      } else {
        setError('챗봇 수정에 실패했습니다.');
      }
    } catch (error) {
      console.error('Error updating chatbot:', error);
      setError('챗봇 수정 중 오류가 발생했습니다.');
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

  if (!chatbot) {
    return <div>Loading...</div>;
  }

  return (
    <div className="edit-chatbot-container">
      <h2>챗봇 수정</h2>
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
          <button type="button" onClick={generateProfileImage}>프로필 이미지 재생성</button>
        </div>
        {error && <p className="error-message">{error}</p>}
        <button type="submit">변경 사항 저장</button>
      </form>
    </div>
  );
}

// ChatHistory 컴포넌트
function ChatHistory({ user }) {
  const [chatbots, setChatbots] = useState([]);
  const [selectedChatbot, setSelectedChatbot] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
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

  const fetchChatHistory = async (chatbotId) => {
    try {
      const response = await axios.get(`/api/chat_history?username=${user.username}&chatbot_id=${chatbotId}`);
      if (response.data.status === 'success') {
        setChatHistory(response.data.chat_history);
      } else {
        setError('대화 내역을 불러오는데 실패했습니다.');
      }
    } catch (error) {
      console.error('Error fetching chat history:', error);
      setError('대화 내역을 불러오는 중 오류가 발생했습니다.');
    }
  };

  const handleChatbotSelect = (chatbot) => {
    setSelectedChatbot(chatbot);
    fetchChatHistory(chatbot._id);
  };

  const deleteChatHistory = async (historyId) => {
    if (window.confirm('정말로 이 대화 내역을 삭제하시겠습니까?')) {
      try {
        const response = await axios.post('/api/delete_chat_history', {
          history_id: historyId,
          username: user.username
        });
        if (response.data.status === 'success') {
          fetchChatHistory(selectedChatbot._id);
        } else {
          setError('대화 내역 삭제에 실패했습니다.');
        }
      } catch (error) {
        console.error('Error deleting chat history:', error);
        setError('대화 내역 삭제 중 오류가 발생했습니다.');
      }
    }
  };

  return (
    <div className="chat-history-container">
      <h2>대화 내역 확인</h2>
      {error && <p className="error-message">{error}</p>}
      <div className="chatbot-list">
        <h3>챗봇 목록</h3>
        {chatbots.map((chatbot) => (
          <button key={chatbot._id} onClick={() => handleChatbotSelect(chatbot)}>
            {chatbot.name}
          </button>
        ))}
      </div>
      {selectedChatbot && (
        <div className="chat-history">
          <h3>{selectedChatbot.name}의 대화 내역</h3>
          {chatHistory.map((history) => (
            <div key={history._id} className="history-entry">
              <p>대화 시간: {new Date(history.timestamp).toLocaleString()}</p>
              {history.messages.map((message, index) => (
                <div key={index} className={`message ${message.role}`}>
                  <p>{message.content}</p>
                </div>
              ))}
              <button onClick={() => deleteChatHistory(history._id)}>이 대화 내역 삭제</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// UsageData 컴포넌트
function UsageData() {
  const [usageData, setUsageData] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchUsageData();
  }, []);

  const fetchUsageData = async () => {
    try {
      const response = await axios.get('/api/usage_data');
      if (response.data.status === 'success') {
        setUsageData(response.data.usage_logs);
      } else {
        setError('사용량 데이터를 불러오는데 실패했습니다.');
      }
    } catch (error) {
      console.error('Error fetching usage data:', error);
      setError('사용량 데이터를 불러오는 중 오류가 발생했습니다.');
    }
  };

  return (
    <div className="usage-data-container">
      <h2>AI 모델 사용량 데이터</h2>
      {error && <p className="error-message">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>사용자</th>
            <th>모델</th>
            <th>사용 시간</th>
            <th>토큰 수</th>
          </tr>
        </thead>
        <tbody>
          {usageData.map((log) => (
            <tr key={log._id}>
              <td>{log.username}</td>
              <td>{log.model_name}</td>
              <td>{new Date(log.timestamp).toLocaleString()}</td>
              <td>{log.tokens_used}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
