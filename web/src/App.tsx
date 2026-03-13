import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

interface ToolEvent {
  tool: string
  input?: Record<string, unknown>
  output?: string
}

interface MessageItem {
  role: 'user' | 'assistant'
  content: string
  tools?: ToolEvent[]
}

const SESSION_ID = crypto.randomUUID?.() ?? `s-${Date.now()}`

function ToolCallBlock({ tool, collapsed: initCollapsed }: { tool: ToolEvent; collapsed?: boolean }) {
  const [collapsed, setCollapsed] = useState(initCollapsed ?? true)

  const detail = tool.output
    ? tool.output
    : tool.input
      ? JSON.stringify(tool.input, null, 2)
      : ''

  return (
    <div className={`tool-call ${collapsed ? 'collapsed' : ''}`}>
      <div className="tool-call-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="icon">{collapsed ? '▶' : '▼'}</span>
        <span>{tool.output ? '✅' : '⏳'} {tool.tool}</span>
      </div>
      {!collapsed && detail && <div className="tool-call-body">{detail}</div>}
    </div>
  )
}

function ThinkingIndicator() {
  return (
    <div className="thinking">
      <div className="thinking-dots">
        <span /><span /><span />
      </div>
      <span>思考中...</span>
    </div>
  )
}

export default function App() {
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentTools, setCurrentTools] = useState<ToolEvent[]>([])
  const [streamingText, setStreamingText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingText, currentTools, scrollToBottom])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const msg = input.trim()
    if (!msg || loading) return

    setInput('')
    setLoading(true)
    setStreamingText('')
    setCurrentTools([])

    const userMessage: MessageItem = { role: 'user', content: msg }
    setMessages(prev => [...prev, userMessage])

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: SESSION_ID }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No reader')

      const decoder = new TextDecoder()
      let buffer = ''
      let fullText = ''
      const tools: ToolEvent[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          try {
            const evt = JSON.parse(raw)

            if (evt.type === 'token') {
              fullText += evt.data
              setStreamingText(fullText)
            } else if (evt.type === 'tool_start') {
              const info = JSON.parse(evt.data)
              tools.push({ tool: info.tool, input: info.input })
              setCurrentTools([...tools])
            } else if (evt.type === 'tool_end') {
              const info = JSON.parse(evt.data)
              const idx = tools.findIndex(t => t.tool === info.tool && !t.output)
              if (idx >= 0) {
                tools[idx] = { ...tools[idx], output: info.output }
                setCurrentTools([...tools])
              }
            } else if (evt.type === 'done') {
              // stream finished
            }
          } catch {
            // skip malformed event
          }
        }
      }

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: fullText, tools: tools.length > 0 ? tools : undefined },
      ])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `请求失败: ${err instanceof Error ? err.message : String(err)}` },
      ])
    } finally {
      setLoading(false)
      setStreamingText('')
      setCurrentTools([])
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const autoResize = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 150) + 'px'
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Truverse Agent</h1>
        <span>ReAct + ClickHouse</span>
      </header>

      <div className="messages">
        {messages.length === 0 && !loading && (
          <div className="empty-state">
            <h2>Truverse 电商数据分析助手</h2>
            <p>
              基于 ReAct 多轮推理，可以直接查询 ClickHouse 数据库。
              试试问「帮我分析店铺商品的评分分布」或「查看所有在售商品」
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className="message">
            <div className={`message-role ${msg.role}`}>
              {msg.role === 'user' ? '你' : '助手'}
            </div>
            {msg.tools && msg.tools.map((t, j) => (
              <ToolCallBlock key={j} tool={t} collapsed />
            ))}
            <div className="message-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content}
              </ReactMarkdown>
            </div>
          </div>
        ))}

        {loading && (
          <div className="message">
            <div className="message-role assistant">助手</div>
            {currentTools.map((t, j) => (
              <ToolCallBlock key={j} tool={t} collapsed={false} />
            ))}
            {streamingText ? (
              <div className="message-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamingText}
                </ReactMarkdown>
              </div>
            ) : (
              currentTools.length === 0 && <ThinkingIndicator />
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              autoResize(e.target)
            }}
            onKeyDown={handleKeyDown}
            placeholder="输入问题... (Enter 发送, Shift+Enter 换行)"
            rows={1}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {loading ? '分析中...' : '发送'}
          </button>
        </form>
      </div>
    </div>
  )
}
