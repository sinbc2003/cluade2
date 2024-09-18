import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Switch, Redirect } from 'react-router-dom';
import axios from 'axios';

// 컴포넌트 임포트
import Login from './components/Login';
import ChangePassword from './components/ChangePassword';
import Home from './components/Home';
import CreateChatbot from './components/CreateChatbot';
import AvailableChatbots from './components/AvailableChatbots';
import SharedChatbots from './components/SharedChatbots';
import ChatbotPage from './components/ChatbotPage';
import SharedChatbotPage from './components/SharedChatbotPage';
import ChatHistory from './components/ChatHistory';
import EditChatbot from './components/EditChatbot';
import EditSharedChatbot from './components/EditSharedChatbot';
import PublicChatbotPage from './components/PublicChatbotPage';
import ViewPublicChatHistory from './components/ViewPublicChatHistory';
import UsageData from './components/UsageData';

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

export default App;
