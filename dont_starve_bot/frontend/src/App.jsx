import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import { agentSearch, getAgentHistory, getAgentHistoryItem } from './api/client';
import { generateSessionId } from './utils/session';
import useChat from './hooks/useChat';
import Header from './components/Header';
import ChatTab from './components/ChatTab';
import AgentTab from './components/AgentTab';
import InputBar from './components/InputBar';

export default function DontStarveChatBot() {
  const sessionId = generateSessionId();
  const messagesEndRef = useRef(null);

  // ========== 跨 Tab 共享状态 ==========
  const [activeTab, setActiveTab] = useState('chat');           // 'chat' | 'agent'
  const [inputValue, setInputValue] = useState('');

  // ========== Agent 状态 ==========
  const [agentSteps, setAgentSteps] = useState([]);              // 工具执行步骤
  const [agentAnswer, setAgentAnswer] = useState('');            // Agent 最终回答
  const [isAgentLoading, setIsAgentLoading] = useState(false);
  const [agentHistory, setAgentHistory] = useState([]);          // 搜索历史
  const [showHistory, setShowHistory] = useState(false);         // 显示历史面板

  // ========== 聊天 Tab 数据流 ==========
  const {
    messages, isLoading, loadingSeconds,
    uploadFile, uploadPreview, uploadType, fileInputRef,
    handleSendMessage, handleClearChat, handleFileSelect, handleRemoveFile, handleKeyPress,
  } = useChat(sessionId, { inputValue, setInputValue });

  // 自动滚动到最后
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, agentSteps, agentAnswer, showHistory]);

  // ========== Agent 操作 ==========

  const handleAgentKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAgentSearch();
    }
  };

  const handleAgentSearch = async () => {
    if (!inputValue.trim()) return;

    setAgentAnswer('');
    setAgentSteps([]);
    setIsAgentLoading(true);
    const query = inputValue;
    setInputValue('');

    try {
      const data = await agentSearch(query, sessionId);

      setAgentSteps(data.steps || []);
      setAgentAnswer(data.answer || '');
      // 刷新历史
      loadAgentHistory();
    } catch (error) {
      setAgentAnswer(`❌ 搜索失败: ${error.message}`);
    } finally {
      setIsAgentLoading(false);
    }
  };

  const loadAgentHistory = async () => {
    try {
      const data = await getAgentHistory(sessionId);
      setAgentHistory(data.history || []);
    } catch (e) {
      // 静默失败
    }
  };

  const handleHistoryItemClick = async (searchId) => {
    try {
      const data = await getAgentHistoryItem(sessionId, searchId);
      setAgentSteps(data.steps || []);
      setAgentAnswer(data.answer || '');
      setShowHistory(false);
      scrollToBottom();
    } catch (e) {
      // 静默失败
    }
  };

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    setInputValue('');
    setShowHistory(false);
    if (tab === 'agent') {
      loadAgentHistory();
    }
  };

  const handleToggleHistory = () => {
    setShowHistory(!showHistory);
    if (!showHistory) loadAgentHistory();
  };

  return (
    <div className="app-container">
      <Header activeTab={activeTab} onTabSwitch={handleTabSwitch} onClear={handleClearChat} />

      {/* 消息区域 */}
      <div className="messages-container">
        {activeTab === 'chat' ? (
          <ChatTab messages={messages} isLoading={isLoading} loadingSeconds={loadingSeconds} />
        ) : (
          <AgentTab
            agentSteps={agentSteps}
            agentAnswer={agentAnswer}
            isAgentLoading={isAgentLoading}
            agentHistory={agentHistory}
            showHistory={showHistory}
            onHistoryItemClick={handleHistoryItemClick}
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <InputBar
        activeTab={activeTab}
        inputValue={inputValue}
        onInputChange={(e) => setInputValue(e.target.value)}
        onKeyPress={activeTab === 'chat' ? handleKeyPress : handleAgentKeyPress}
        onSend={activeTab === 'chat' ? handleSendMessage : handleAgentSearch}
        isLoading={isLoading}
        isAgentLoading={isAgentLoading}
        uploadFile={uploadFile}
        uploadType={uploadType}
        uploadPreview={uploadPreview}
        onRemoveFile={handleRemoveFile}
        onFileSelect={handleFileSelect}
        fileInputRef={fileInputRef}
        showHistory={showHistory}
        onToggleHistory={handleToggleHistory}
      />
    </div>
  );
}
