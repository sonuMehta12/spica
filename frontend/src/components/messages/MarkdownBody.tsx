import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { color, font } from '../../theme';
import { agentVoice } from './bubble';

/**
 * The agent's prose, rendered.
 *
 * The model already writes `**bold**` and the odd list; until now that reached
 * the screen as literal asterisks. Rendering it is the fix — but the *voice*
 * rules still hold: the serif, in ink, one size. A `#` from the model renders
 * as an emphasised line, not a title, because a reply is a sentence, not a
 * document. Links open in a new tab; raw HTML is never rendered.
 *
 * Emphasis is the serif's medium weight: the face is loaded at 400 and 500
 * only, and a synthesised bold smears.
 */
export default function MarkdownBody({ text }: { text: string }) {
  return (
    <div style={agentVoice} className="cx-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          // Headings flatten to an emphasised line — one voice, one size.
          h1: ({ children }) => <p style={{ margin: '0 0 4px', fontWeight: 500 }}>{children}</p>,
          h2: ({ children }) => <p style={{ margin: '0 0 4px', fontWeight: 500 }}>{children}</p>,
          h3: ({ children }) => <p style={{ margin: '0 0 4px', fontWeight: 500 }}>{children}</p>,
          p: ({ children }) => <p style={{ margin: '0 0 6px' }}>{children}</p>,
          ul: ({ children }) => <ul style={{ margin: '2px 0 6px', paddingLeft: 20 }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: '2px 0 6px', paddingLeft: 20 }}>{children}</ol>,
          li: ({ children }) => <li style={{ margin: '1px 0' }}>{children}</li>,
          strong: ({ children }) => <strong style={{ fontWeight: 500 }}>{children}</strong>,
          // Numbers and names the model quotes back — the interface face says
          // "this is data".
          code: ({ children }) => (
            <code style={{ fontFamily: font.sans, fontSize: 13.5, color: color.muted }}>
              {children}
            </code>
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer" style={{ color: color.brand }}>
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', margin: '4px 0 6px' }}>
              <table style={{ borderCollapse: 'collapse', fontFamily: font.sans, fontSize: 13 }}>{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th style={{ textAlign: 'left', padding: '2px 10px 2px 0', fontFamily: font.sans,
                         fontSize: 11, color: color.faint, fontWeight: 500 }}>{children}</th>
          ),
          td: ({ children }) => <td style={{ padding: '2px 10px 2px 0' }}>{children}</td>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
