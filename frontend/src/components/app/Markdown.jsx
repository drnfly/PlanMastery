import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const Markdown = ({ text }) => (
  <div className="md text-sm leading-relaxed"><ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown></div>
);
