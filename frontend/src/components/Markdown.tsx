import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';

export default function Markdown({ content }: { content: string }) {
  return <div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}
    components={{ a: ({ href, children, ...props }) => <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>,
      table: ({ children }) => <div className="table-scroll"><table>{children}</table></div> }}>{content}</ReactMarkdown></div>;
}
