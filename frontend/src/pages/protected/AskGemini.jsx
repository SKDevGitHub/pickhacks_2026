import { useState, useRef, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import DOMPurify from 'dompurify';

const WELCOME = `Hi! I'm **Chartr AI** — your environmental technology advisor.

I have real-time access to all the emerging technology data in our system, including Power, Pollution, and Water externality forecasts.

**Try asking me things like:**
- "Compare the water usage of Data Centers vs Semiconductor Plants"
- "Which technology has the highest pollution impact?"
- "What are the power implications of scaling autonomous vehicles?"
- "Summarize the environmental tradeoffs of AI Campus deployments"

How can I help your team today?`;

export default function AskGemini() {
    const { getAccessTokenSilently, getAccessTokenWithPopup } = useAuth0();
    const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
    const [messages, setMessages] = useState([
        { role: 'assistant', content: WELCOME },
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, loading]);

    // Focus input on mount
    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    async function getApiToken() {
        try {
            if (audience) {
                return await getAccessTokenSilently({ authorizationParams: { audience } });
            }
            return await getAccessTokenSilently();
        } catch (err) {
            if (err?.error === 'consent_required' || err?.error === 'login_required') {
                if (audience) {
                    return getAccessTokenWithPopup({ authorizationParams: { audience } });
                }
                return getAccessTokenWithPopup();
            }
            throw err;
        }
    }

    async function handleSend(e) {
        e?.preventDefault();
        const text = input.trim();
        if (!text || loading) return;

        const userMsg = { role: 'user', content: text };
        const newMessages = [...messages, userMsg];
        setMessages(newMessages);
        setInput('');
        setError('');
        setLoading(true);

        try {
            const token = await getApiToken();
            // Only send user/assistant messages (not the initial welcome as-is)
            const chatHistory = newMessages
                .filter((_, i) => i > 0 || newMessages[0].role === 'user')
                .map((m) => ({ role: m.role, content: m.content }));

            // If welcome message was the only assistant msg, start fresh for API
            const apiMessages = chatHistory.length > 0 ? chatHistory : [userMsg];

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ messages: apiMessages }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `API error ${res.status}`);
            }

            const data = await res.json();
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: data.reply },
            ]);
        } catch (err) {
            setError(err.message || 'Something went wrong');
        } finally {
            setLoading(false);
            inputRef.current?.focus();
        }
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    function formatMarkdown(text) {
        const escaped = String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');

        // Minimal Markdown rendering for chat bubbles
        let html = escaped
            // code blocks
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            // inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // bold
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            // italic
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // headers
            .replace(/^### (.+)$/gm, '<h4>$1</h4>')
            .replace(/^## (.+)$/gm, '<h3>$1</h3>')
            // bullet lists
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            // wrap consecutive <li> in <ul>
            .replace(/((?:<li>.*<\/li>\s*)+)/g, '<ul>$1</ul>')
            // line breaks (but not inside pre/code)
            .replace(/\n/g, '<br />');

        return DOMPurify.sanitize(html, {
            ALLOWED_TAGS: ['pre', 'code', 'strong', 'em', 'h3', 'h4', 'ul', 'li', 'br', 'p'],
            ALLOWED_ATTR: [],
        });
    }

    return (
        <div className="chat-page">
            <div className="chat-header">
                <div className="chat-header-icon">✦</div>
                <div>
                    <h1 className="chat-header-title">Chartr AI</h1>
                    <p className="chat-header-subtitle">
                        AI-powered environmental technology advisor · Powered by Google Gemini
                    </p>
                </div>
            </div>

            <div className="chat-body" ref={scrollRef}>
                {messages.map((msg, i) => (
                    <div
                        key={i}
                        className={`chat-bubble chat-bubble--${msg.role}`}
                    >
                        {msg.role === 'assistant' && (
                            <span className="chat-bubble-avatar">✦</span>
                        )}
                        <div
                            className="chat-bubble-content"
                            dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.content) }}
                        />
                    </div>
                ))}

                {loading && (
                    <div className="chat-bubble chat-bubble--assistant">
                        <span className="chat-bubble-avatar">✦</span>
                        <div className="chat-bubble-content chat-typing">
                            <span /><span /><span />
                        </div>
                    </div>
                )}

                {error && (
                    <div className="chat-error">{error}</div>
                )}
            </div>

            <form className="chat-input-bar" onSubmit={handleSend}>
                <textarea
                    ref={inputRef}
                    className="chat-input"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about technologies, environmental impact, comparisons…"
                    rows={1}
                    disabled={loading}
                />
                <button
                    type="submit"
                    className="chat-send-btn"
                    disabled={!input.trim() || loading}
                >
                    {loading ? '…' : '↑'}
                </button>
            </form>
        </div>
    );
}
