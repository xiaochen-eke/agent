// Markdown 简单渲染（支持加粗、斜体、代码块）
export const renderMarkdown = (text) => {
  // 先转义 HTML 防止注入
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  // 粗体 **...**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 单行内的斜体 *...*（不跨行，不含空格边界）
  html = html.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
  // 行内代码 `...`
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');
  // 【...】高亮
  html = html.replace(/【(.+?)】/g, '<span class="highlight-bracket">【$1】</span>');
  // 换行转 <br/>
  html = html.replace(/\n/g, '<br/>');
  return html;
};
