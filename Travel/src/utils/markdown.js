import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({
  gfm: true,
  breaks: true,
});

/**
 * 把模型回复的 Markdown 转成可安全插入页面的 HTML。
 * 流式输出时内容可能尚未闭合（如未写完的列表），marked 仍能尽量渲染。
 */
export function renderMarkdown(source) {
  const html = marked.parse(String(source || ""), { async: false });
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}
