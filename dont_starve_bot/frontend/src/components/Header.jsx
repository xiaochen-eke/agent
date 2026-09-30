import React from 'react';

// 顶部：标题 + Tab 切换 + 清空按钮
const Header = ({ activeTab, onTabSwitch, onClear }) => (
  <div className="app-header">
    <div className="header-content">
      <h1>{activeTab === 'chat' ? '🎮 饥荒游戏攻略助手' : '🌐 联网搜索助手'}</h1>
      <p>{activeTab === 'chat' ? '基于深度攻略文档 + 大模型的精准回答' : '文件搜索 · 内容检索 · 网页搜索'}</p>
    </div>
    <div className="header-tabs">
      <button className={`tab-btn ${activeTab === 'chat' ? 'tab-active' : ''}`}
              onClick={() => onTabSwitch('chat')}>
        🎮 游戏攻略
      </button>
      <button className={`tab-btn ${activeTab === 'agent' ? 'tab-active' : ''}`}
              onClick={() => onTabSwitch('agent')}>
        🌐 联网搜索
      </button>
    </div>
    <button className="clear-btn" onClick={onClear} title="清空对话">
      🗑️
    </button>
  </div>
);

export default Header;
