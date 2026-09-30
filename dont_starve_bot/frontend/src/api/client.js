// API 客户端：统一管理后端地址与接口封装。
// 后端基址优先取环境变量 REACT_APP_API_BASE_URL，否则回退本地默认值。
export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

// 纯文本对话（RAG）
export const chat = async (message, sessionId, signal) => {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });
  if (!response.ok) throw new Error('网络错误');
  return response.json();
};

// 多模态对话（图片 / 语音），formData 含 file/type/message/session_id
export const multimodalChat = async (formData, signal) => {
  const response = await fetch(`${API_BASE_URL}/api/multimodal/chat`, {
    method: 'POST',
    body: formData,
    signal,
  });
  if (!response.ok) throw new Error('网络错误');
  return response.json();
};

// Agent 联网搜索
export const agentSearch = async (query, sessionId) => {
  const response = await fetch(`${API_BASE_URL}/api/agent/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId }),
  });
  if (!response.ok) throw new Error('搜索请求失败');
  return response.json();
};

// Agent 搜索历史列表
export const getAgentHistory = async (sessionId) => {
  const response = await fetch(`${API_BASE_URL}/api/agent/history/${sessionId}`);
  if (!response.ok) throw new Error('获取历史失败');
  return response.json();
};

// Agent 单条搜索历史详情
export const getAgentHistoryItem = async (sessionId, searchId) => {
  const response = await fetch(`${API_BASE_URL}/api/agent/history/${sessionId}/${searchId}`);
  if (!response.ok) throw new Error('获取历史详情失败');
  return response.json();
};
