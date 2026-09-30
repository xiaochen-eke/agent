import React from 'react';
import TypeWriter from './TypeWriter';

// 工具图标和标签映射
const getToolIcon = (toolName) => {
  const icons = { search_files: '📁', search_content: '🔎', search_images: '🖼️', list_image_labels: '🏷️', read_file: '📄', web_search: '🌐' };
  return icons[toolName] || '🔧';
};
const getToolLabel = (toolName) => {
  const labels = { search_files: '搜索文件', search_content: '搜索内容', search_images: '搜索图片', list_image_labels: '列出标签', read_file: '读取文件', web_search: '网页搜索' };
  return labels[toolName] || toolName;
};

// 联网搜索 Tab：工具执行步骤 + 回答 + 搜索历史面板
const AgentTab = ({ agentSteps, agentAnswer, isAgentLoading, agentHistory, showHistory, onHistoryItemClick }) => (
  <>
    {showHistory ? (
      /* 搜索历史面板 */
      <div className="history-panel">
        <h3>📋 搜索历史</h3>
        {agentHistory.length === 0 ? (
          <p className="history-empty">暂无搜索记录</p>
        ) : (
          agentHistory.map((item) => (
            <div key={item.id} className="history-item"
                 onClick={() => onHistoryItemClick(item.id)}>
              <span className="history-query">{item.query}</span>
              <span className="history-time">
                {new Date(item.created_at).toLocaleString()}
              </span>
              <span className="history-tools">
                🔧 {item.tool_calls_count} 次工具调用
              </span>
            </div>
          ))
        )}
      </div>
    ) : (
      /* 搜索结果展示 */
      <div className="agent-result">
        {/* 工具执行步骤 */}
        {agentSteps.length > 0 && (
          <div className="agent-steps">
            <div className="steps-header">
              🔧 工具执行过程 ({agentSteps.length} 步) · {agentSteps[agentSteps.length - 1]?.tool === 'web_search' ? '已联网搜索' : '本地搜索完成'}
            </div>
            {agentSteps.map((step, idx) => (
              <details key={idx} className="step-detail"
                       open={idx === agentSteps.length - 1}>
                <summary className="step-summary">
                  <span className="step-icon">{getToolIcon(step.tool)}</span>
                  <span className="step-name">{getToolLabel(step.tool)}</span>
                  <span className="step-args">
                    {JSON.stringify(step.args).substring(0, 80)}
                  </span>
                  {idx === agentSteps.length - 1 && isAgentLoading && (
                    <span className="step-spinner">⏳</span>
                  )}
                </summary>
                <pre className="step-result">{step.result_preview}</pre>
              </details>
            ))}
          </div>
        )}

        {/* Agent 回答 */}
        {agentAnswer && (
          <div className="message-wrapper message-bot">
            <div className="message-content message-bot">
              <div className="bot-message">
                <TypeWriter text={agentAnswer} speed={25} />
              </div>
              <span className="message-time">
                {new Date().toLocaleTimeString()}
              </span>
            </div>
          </div>
        )}

        {/* 加载中 */}
        {isAgentLoading && !agentAnswer && agentSteps.length === 0 && (
          <div className="message-wrapper message-bot">
            <div className="message-content message-bot loading">
              <div className="typing-indicator"><span></span><span></span><span></span></div>
              <span>正在联网搜索...</span>
            </div>
          </div>
        )}
      </div>
    )}
  </>
);

export default AgentTab;
