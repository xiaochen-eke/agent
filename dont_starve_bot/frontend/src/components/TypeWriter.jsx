import React, { useState, useEffect, useRef } from 'react';
import { renderMarkdown } from '../utils/markdown';

// 打字机效果（抗重渲染版）
const TypeWriter = React.memo(({ text = '', speed = 25 }) => {
  const [plain, setPlain] = useState('');
  const [done, setDone] = useState(false);
  const idxRef = useRef(0);
  const prevRef = useRef('');
  const timerRef = useRef(null);

  useEffect(() => {
    // 新消息 → 重置
    if (text !== prevRef.current) {
      prevRef.current = text;
      idxRef.current = 0;
      setPlain('');
      setDone(false);
      if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    }

    if (!text) return;

    const tick = () => {
      const i = idxRef.current;
      if (i < text.length) {
        const c = text[i];
        const step = c.charCodeAt(0) > 127 ? 1 : Math.min(2, text.length - i);
        idxRef.current = i + step;
        setPlain(text.slice(0, i + step));
        timerRef.current = setTimeout(tick, c === '\n' ? speed * 4 : speed);
      } else {
        setDone(true);
      }
    };

    timerRef.current = setTimeout(tick, idxRef.current === 0 ? 200 : 30);

    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [text]);

  // 打字期间：纯文本 + <br>；完成后：完整 markdown
  const display = done ? renderMarkdown(text) : plain.replace(/\n/g, '<br/>');
  return <div dangerouslySetInnerHTML={{ __html: display }} />;
});

export default TypeWriter;
