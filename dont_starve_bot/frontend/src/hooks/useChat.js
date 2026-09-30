import { useState, useRef } from 'react';
import { API_BASE_URL, chat, multimodalChat } from '../api/client';

// 聊天 Tab 的数据流封装：消息、加载态、多模态上传、发送逻辑
const useChat = (sessionId, { inputValue, setInputValue }) => {
  const [messages, setMessages] = useState([
    {
      id: 0,
      type: 'bot',
      content: '👋 欢迎来到《饥荒 Don\'t Starve》游戏攻略助手！\n\n我是一位资深玩家，精通所有生存策略、食物机制、季节过渡等内容。\n\n🎮 **你可以问我：**\n- 新手前期如何生存？\n- 理智值怎么管理？\n- 第几天应该造什么建筑？\n- 如何度过冬季？\n- 某个生物怎么对付？\n\n🖼️ **新增多模态功能：**\n- 上传游戏截图，自动识别场景和危险\n- 上传语音提问，自动转录回答\n\n开始提问吧！',
      sources: [],
      apis: [],
      timestamp: new Date()
    }
  ]);

  const [isLoading, setIsLoading] = useState(false);
  const [loadingSeconds, setLoadingSeconds] = useState(0);  // 加载计时器
  const loadingTimerRef = useRef(null);                       // 计时器句柄

  const [uploadFile, setUploadFile] = useState(null);         // 上传的文件对象
  const [uploadPreview, setUploadPreview] = useState('');     // 预览 URL
  const [uploadType, setUploadType] = useState('');           // 'image' | 'audio' | ''
  const fileInputRef = useRef(null);

  // 处理回车发送
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFileSelect = (e, type) => {
    const file = e.target.files[0];
    if (!file) return;

    // 检查文件大小（限制 10MB）
    if (file.size > 10 * 1024 * 1024) {
      alert('文件过大，请选择 10MB 以内的文件');
      return;
    }

    setUploadFile(file);
    setUploadType(type);

    // 生成预览
    const url = URL.createObjectURL(file);
    setUploadPreview(url);
  };

  const handleRemoveFile = () => {
    if (uploadPreview) {
      URL.revokeObjectURL(uploadPreview);
    }
    setUploadFile(null);
    setUploadPreview('');
    setUploadType('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClearChat = () => {
    if (window.confirm('确定要清空对话记录吗？')) {
      setMessages([messages[0]]);
      localStorage.removeItem('sessionId');
    }
  };

  const handleSendMessage = async () => {
    const hasFile = uploadFile !== null;
    if (!inputValue.trim() && !hasFile) return;

    const text = inputValue || (uploadType === 'image' ? '请分析这张图片' : '请回答语音中的问题');
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: text,
      timestamp: new Date(),
      // 多模态附件
      attachment: uploadFile ? {
        name: uploadFile.name,
        type: uploadType,
        preview: uploadPreview,
        size: uploadFile.size,
      } : null,
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setLoadingSeconds(0);

    // 启动加载计时器（每秒 +1）
    loadingTimerRef.current = setInterval(() => {
      setLoadingSeconds(s => s + 1);
    }, 1000);

    // AbortController 120s 超时，防止前端无限等待
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    try {
      let data;
      if (hasFile) {
        // 多模态请求
        const formData = new FormData();
        formData.append('file', uploadFile);
        formData.append('type', uploadType);
        formData.append('message', text);
        formData.append('session_id', sessionId);
        data = await multimodalChat(formData, controller.signal);
      } else {
        // 纯文本请求
        data = await chat(text, sessionId, controller.signal);
      }
      clearTimeout(timeoutId);

      const timingInfo = data.timing || {};
      // 构建耗时脚注
      let timingFootnote = '';
      if (data.elapsed_ms) {
        const sec = (data.elapsed_ms / 1000).toFixed(1);
        timingFootnote = `⏱ ${sec}s`;
        if (timingInfo.rag_score_ms > 100) {
          timingFootnote += `（检索 ${(timingInfo.rag_score_ms / 1000).toFixed(1)}s`;
          if (timingInfo.generation_ms > 0) {
            timingFootnote += ` + 推理 ${(timingInfo.generation_ms / 1000).toFixed(1)}s`;
          }
          timingFootnote += '）';
        }
      }

      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: data.response,
        sources: data.sources || [],
        apis: data.apis_used || [],
        intent: data.intent || [],
        engine: data.engine || 'GLM-5',
        plan: data.plan || [],
        tool_calls: data.tool_calls || [],
        memory: data.memory || {},
        trace: data.trace || [],
        timing: timingInfo,
        timingFootnote,
        elapsedMs: data.elapsed_ms || 0,
        // 多模态元信息
        inputType: data.input_type || 'text',
        parsedInfo: data.parsed_info || {},
        multimodalEngine: data.multimodal_engine || '',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, botMessage]);

      // 清除上传
      handleRemoveFile();
    } catch (error) {
      clearTimeout(timeoutId);
      const isTimeout = error.name === 'AbortError';
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: isTimeout
          ? '⏳ 请求超时（超过 120 秒），请稍后再试。如果频繁出现，可以尝试简化问题。'
          : `❌ 连接失败: ${error.message}\n请确保后端服务正在运行 (${API_BASE_URL})`,
        sources: [],
        apis: [],
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      handleRemoveFile();
    } finally {
      clearInterval(loadingTimerRef.current);
      loadingTimerRef.current = null;
      setIsLoading(false);
    }
  };

  return {
    messages,
    isLoading,
    loadingSeconds,
    uploadFile,
    uploadPreview,
    uploadType,
    fileInputRef,
    handleSendMessage,
    handleClearChat,
    handleFileSelect,
    handleRemoveFile,
    handleKeyPress,
  };
};

export default useChat;
