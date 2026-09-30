import React from 'react';
import MessageBubble from './MessageBubble';

// 游戏攻略 Tab：消息列表 + 加载指示
const ChatTab = ({ messages, isLoading, loadingSeconds }) => (
  <>
    {messages.map((msg) => (
      <MessageBubble key={msg.id} msg={msg} />
    ))}

    {isLoading && (
      <div className="message-wrapper message-bot">
        <div className="message-content message-bot loading">
          <div className="typing-indicator"><span></span><span></span><span></span></div>
          <span>正在查阅知识库...{loadingSeconds > 0 && ` (已等待 ${loadingSeconds}s)`}</span>
        </div>
      </div>
    )}
  </>
);

export default ChatTab;
