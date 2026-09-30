import React from 'react';
import TypeWriter from './TypeWriter';

// 单条消息（用户 / 机器人），含附件、来源、意图、决策过程、计划、工具调用、记忆、耗时等元信息
const MessageBubble = ({ msg }) => (
  <div className={`message-wrapper message-${msg.type}`}>
    <div className={`message-content message-${msg.type}`}>
      {msg.type === 'user' ? (
        <div className="user-message">
          {/* 多模态附件展示 */}
          {msg.attachment && msg.attachment.type === 'image' && (
            <div className="message-attachment">
              <div className="attachment-label">🖼️ {msg.attachment.name}</div>
              <img src={msg.attachment.preview} alt="上传的图片" className="attachment-img" />
            </div>
          )}
          {msg.attachment && msg.attachment.type === 'audio' && (
            <div className="message-attachment">
              <div className="attachment-label">🎤 {msg.attachment.name}</div>
              <audio src={msg.attachment.preview} controls className="attachment-audio" />
            </div>
          )}
          {msg.content}
        </div>
      ) : (
        <div className="bot-message">
          <TypeWriter text={msg.content} speed={25} />

          {/* 多模态解析信息 */}
          {msg.inputType && msg.inputType !== 'text' && (
            <div className="message-multimodal">
              <span className="multimodal-tag">🔍 {msg.inputType === 'image' ? '图片解析' : '语音转录'} ({msg.multimodalEngine || 'unknown'})</span>
              {msg.parsedInfo && msg.parsedInfo.objects && msg.parsedInfo.objects.length > 0 && (
                <div className="multimodal-detail">
                  {msg.parsedInfo.objects.slice(0, 6).map((obj, i) => (
                    <span key={i} className="multimodal-obj">{obj}</span>
                  ))}
                </div>
              )}
              {msg.parsedInfo && msg.parsedInfo.scene && (
                <div className="multimodal-detail">
                  <span className="multimodal-obj">📍 {msg.parsedInfo.scene}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {msg.sources && msg.sources.length > 0 && (
        <div className="message-sources">
          <div className="sources-label">📚 信息来源：</div>
          {msg.sources.map((source, idx) => (
            <span key={idx} className="source-tag">{source}</span>
          ))}
        </div>
      )}

      {msg.apis && msg.apis.length > 0 && (
        <div className="message-apis">
          <span className="api-tag">🔗 APIs: {msg.apis.join(', ')}</span>
        </div>
      )}

      {msg.intent && msg.intent.length > 0 && (
        <div className="message-intent">
          <span className="intent-tag">🎯 识别: {msg.intent.join(' + ')}</span>
        </div>
      )}

      {/* Agent 决策过程 */}
      {msg.trace && msg.trace.length > 0 && (
        <details className="message-trace">
          <summary className="trace-header">🧠 Agent 决策过程 ({msg.trace.length} 步)</summary>
          <div className="trace-body">
            {msg.trace.map((t, idx) => (
              <div key={idx} className="trace-step">
                <div className="trace-step-header">
                  <span className="trace-num">[{t.step}]</span>
                  <span className="trace-title">{t.title}</span>
                </div>
                <div className="trace-detail">{t.detail}</div>
                <div className="trace-result">→ {t.result}</div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Agent 计划 */}
      {msg.plan && msg.plan.length > 0 && (
        <div className="message-plan">
          <div className="plan-label">📋 Agent 计划 ({msg.plan.length}步)</div>
          {msg.plan.map((step, idx) => (
            <span key={idx} className="plan-step">{idx + 1}. {step}</span>
          ))}
        </div>
      )}

      {/* 工具调用 */}
      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <div className="message-tools">
          <div className="tools-label">🔧 工具调用</div>
          {msg.tool_calls.map((tc, idx) => (
            <details key={idx} className="tool-detail">
              <summary className="tool-summary">{tc.tool}</summary>
              <pre className="tool-result">{tc.result}</pre>
            </details>
          ))}
        </div>
      )}

      {/* 记忆更新 */}
      {msg.memory && Object.keys(msg.memory).length > 0 && (
        <div className="message-memory">
          <span className="memory-tag">🧠 记忆更新: {Object.entries(msg.memory).slice(0, 3).map(([k, v]) => `${k}=${v}`).join(' | ')}</span>
        </div>
      )}

      {msg.engine && (
        <div className="message-engine">
          <span className="engine-tag">🧠 {msg.engine}</span>
        </div>
      )}

      {/* ⏱ 耗时展示 */}
      {msg.timingFootnote && (
        <div className="message-timing">
          <span className="timing-tag">{msg.timingFootnote}</span>
        </div>
      )}

      <span className="message-time">{msg.timestamp.toLocaleTimeString()}</span>
    </div>
  </div>
);

export default MessageBubble;
