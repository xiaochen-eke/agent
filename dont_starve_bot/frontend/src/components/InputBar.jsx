import React from 'react';

// 底部输入区：历史切换、多模态上传、文本输入、发送按钮、提示
const InputBar = ({
  activeTab,
  inputValue,
  onInputChange,
  onKeyPress,
  onSend,
  isLoading,
  isAgentLoading,
  uploadFile,
  uploadType,
  uploadPreview,
  onRemoveFile,
  onFileSelect,
  fileInputRef,
  showHistory,
  onToggleHistory,
}) => (
  <div className="input-container">
    {activeTab === 'agent' && (
      <button className="history-toggle" onClick={onToggleHistory}>
        {showHistory ? '✕ 关闭历史' : '📋 搜索历史'}
      </button>
    )}

    {/* 多模态上传预览 */}
    {uploadFile && (
      <div className="upload-preview">
        <button className="upload-remove" onClick={onRemoveFile} title="移除文件">✕</button>
        {uploadType === 'image' ? (
          <div className="upload-preview-content">
            <img src={uploadPreview} alt="预览" className="upload-preview-img" />
            <span className="upload-preview-name">🖼️ {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)</span>
          </div>
        ) : (
          <div className="upload-preview-content">
            <audio src={uploadPreview} controls className="upload-preview-audio" />
            <span className="upload-preview-name">🎤 {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)</span>
          </div>
        )}
      </div>
    )}

    {/* 隐藏的文件选择器 */}
    <input
      ref={fileInputRef}
      type="file"
      accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
      onChange={(e) => onFileSelect(e, 'image')}
      style={{ display: 'none' }}
      id="image-upload-input"
    />
    <input
      type="file"
      accept="audio/wav,audio/mp3,audio/m4a,audio/ogg,audio/flac,audio/webm"
      onChange={(e) => onFileSelect(e, 'audio')}
      style={{ display: 'none' }}
      id="audio-upload-input"
    />

    <div className="input-wrapper">
      {/* 多模态上传按钮（仅游戏攻略 Tab 显示） */}
      {activeTab === 'chat' && (
        <div className="upload-buttons">
          <button
            className={`upload-btn ${uploadType === 'image' ? 'upload-btn-active' : ''}`}
            onClick={() => document.getElementById('image-upload-input').click()}
            disabled={isLoading}
            title="上传游戏截图"
          >
            🖼️
          </button>
          <button
            className={`upload-btn ${uploadType === 'audio' ? 'upload-btn-active' : ''}`}
            onClick={() => document.getElementById('audio-upload-input').click()}
            disabled={isLoading}
            title="上传语音问题"
          >
            🎤
          </button>
        </div>
      )}

      <textarea
        value={inputValue}
        onChange={onInputChange}
        onKeyPress={onKeyPress}
        placeholder={
          uploadFile
            ? (uploadType === 'image'
              ? '可选：添加文字说明（如"图中的蜘蛛怎么打"）...'
              : '可选：补充文字说明...')
            : (activeTab === 'chat'
              ? '输入你的问题... 🖼️上传截图 | 🎤上传语音 | Shift+Enter 换行 | Enter 发送'
              : '输入搜索内容... 如：搜索今天的热点新闻 / 查找D盘所有PDF文件')
        }
        disabled={isLoading || isAgentLoading}
        rows="3"
        className="message-input"
      />
      <button
        onClick={onSend}
        disabled={(isLoading || isAgentLoading) || (!inputValue.trim() && !uploadFile)}
        className="send-btn"
        title={activeTab === 'chat' ? '发送 (Enter)' : '搜索 (Enter)'}
      >
        {(isLoading || isAgentLoading) ? '⏳' : (activeTab === 'chat' ? '发送' : '搜索')}
      </button>
    </div>
    <div className="input-hints">
      <span>
        {activeTab === 'chat'
          ? '💡 提示：询问具体的生存策略、建筑顺序、季节过渡等内容 | 🖼️ 可上传游戏截图 | 🎤 可上传语音提问'
          : '🌐 可搜索：文件 | 文件内容 | 图片 | 网页（联网）  ·  输入描述即可，Agent 自动选择工具'}
      </span>
    </div>
  </div>
);

export default InputBar;
