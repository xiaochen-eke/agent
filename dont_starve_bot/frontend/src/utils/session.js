// 生成 Session ID（持久化到 localStorage，保证同浏览器多轮对话共用）
export const generateSessionId = () => {
  if (!localStorage.getItem('sessionId')) {
    localStorage.setItem('sessionId', `session_${Date.now()}`);
  }
  return localStorage.getItem('sessionId');
};
