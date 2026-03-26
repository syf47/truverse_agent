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

interface DeskAuditResult {
  passed: boolean
  score: number
  threshold: number
  summary: string
  issues: string[]
  suggestions: string[]
  handling_advice: string
  handling_advice_json: Record<string, unknown>
  issue_annotations: DeskAuditIssueAnnotation[]
  annotated_image_base64?: string | null
  reference_mode: string
}

interface DeskAuditIssueAnnotation {
  label: string
  detail?: string | null
  box: number[]
}

interface DeskAuditReferenceStatus {
  configured: boolean
  filename?: string | null
  updated_at?: number | null
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

function formatUpdatedAt(timestamp?: number | null) {
  if (!timestamp) return '未保存'
  return new Date(timestamp * 1000).toLocaleString()
}

export default function App() {
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [currentTools, setCurrentTools] = useState<ToolEvent[]>([])
  const [streamingText, setStreamingText] = useState('')

  const [referenceFile, setReferenceFile] = useState<File | null>(null)
  const [referencePreview, setReferencePreview] = useState('')
  const [referenceSaving, setReferenceSaving] = useState(false)
  const [referenceStatus, setReferenceStatus] = useState<DeskAuditReferenceStatus | null>(null)

  const [auditFile, setAuditFile] = useState<File | null>(null)
  const [auditPreview, setAuditPreview] = useState('')
  const [auditNotes, setAuditNotes] = useState('')
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState('')
  const [auditResult, setAuditResult] = useState<DeskAuditResult | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const referenceInputRef = useRef<HTMLInputElement>(null)
  const auditInputRef = useRef<HTMLInputElement>(null)

  const fetchReferenceStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/audit/desk-cleanliness/reference')
      if (!res.ok) return
      const data = await res.json() as DeskAuditReferenceStatus
      setReferenceStatus(data)
    } catch {
      // ignore bootstrap status failures
    }
  }, [])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    fetchReferenceStatus()
  }, [fetchReferenceStatus])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingText, currentTools, scrollToBottom])

  useEffect(() => {
    if (!referenceFile) {
      setReferencePreview('')
      return
    }
    const url = URL.createObjectURL(referenceFile)
    setReferencePreview(url)
    return () => URL.revokeObjectURL(url)
  }, [referenceFile])

  useEffect(() => {
    if (!auditFile) {
      setAuditPreview('')
      return
    }
    const url = URL.createObjectURL(auditFile)
    setAuditPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [auditFile])

  const parseError = async (res: Response) => {
    try {
      const data = await res.json()
      return data.detail ?? `HTTP ${res.status}`
    } catch {
      return `HTTP ${res.status}`
    }
  }

  const handleSaveReference = async () => {
    if (!referenceFile || referenceSaving) return

    setReferenceSaving(true)
    setAuditError('')

    try {
      const form = new FormData()
      form.append('reference_image', referenceFile)

      const res = await fetch('/api/audit/desk-cleanliness/reference', {
        method: 'POST',
        body: form,
      })

      if (!res.ok) {
        throw new Error(await parseError(res))
      }

      const data = await res.json() as DeskAuditReferenceStatus
      setReferenceStatus(data)
      setReferenceFile(null)
      if (referenceInputRef.current) {
        referenceInputRef.current.value = ''
      }
    } catch (err) {
      setAuditError(`保存参考图失败: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setReferenceSaving(false)
    }
  }

  const handleAuditSubmit = async () => {
    if (!auditFile || auditLoading) return

    setAuditLoading(true)
    setAuditError('')
    setAuditResult(null)

    try {
      const form = new FormData()
      form.append('submitted_image', auditFile)
      if (auditNotes.trim()) {
        form.append('notes', auditNotes.trim())
      }

      const res = await fetch('/api/audit/desk-cleanliness', {
        method: 'POST',
        body: form,
      })

      if (!res.ok) {
        throw new Error(await parseError(res))
      }

      const data = await res.json() as DeskAuditResult
      setAuditResult(data)
    } catch (err) {
      setAuditError(`审核失败: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setAuditLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const msg = input.trim()
    if (!msg || chatLoading) return

    setInput('')
    setChatLoading(true)
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
      setChatLoading(false)
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
        <span>ReAct + ClickHouse + Vision Audit</span>
      </header>

      <section className="audit-panel">
        <div className="panel-title-row">
          <div>
            <h2>桌面清洁审核</h2>
            <p>先保存一张干净桌面的标准图，之后员工只需上传待审核照片。</p>
          </div>
          <div className={`reference-badge ${referenceStatus?.configured ? 'ready' : 'missing'}`}>
            {referenceStatus?.configured ? '已保存参考图' : '未保存参考图'}
          </div>
        </div>

        <div className="panel-grid">
          <div className="upload-card">
            <h3>1. 保存标准参考图</h3>
            <p>推荐上传干净整洁、拍摄角度稳定的桌面照片。</p>
            <input
              ref={referenceInputRef}
              type="file"
              accept="image/*"
              onChange={(e) => setReferenceFile(e.target.files?.[0] ?? null)}
            />
            {referencePreview && (
              <img className="preview-image" src={referencePreview} alt="参考图预览" />
            )}
            <button
              className="action-button"
              type="button"
              onClick={handleSaveReference}
              disabled={!referenceFile || referenceSaving}
            >
              {referenceSaving ? '保存中...' : '保存为参考图'}
            </button>
            <div className="upload-meta">
              <span>当前文件：{referenceStatus?.filename ?? '暂无'}</span>
              <span>更新时间：{formatUpdatedAt(referenceStatus?.updated_at)}</span>
            </div>
          </div>

          <div className="upload-card">
            <h3>2. 上传员工照片审核</h3>
            <p>系统会默认拿已保存的参考图进行对比，并输出不卫生点。</p>
            <input
              ref={auditInputRef}
              type="file"
              accept="image/*"
              onChange={(e) => setAuditFile(e.target.files?.[0] ?? null)}
            />
            {auditPreview && (
              <img className="preview-image" src={auditPreview} alt="待审核图片预览" />
            )}
            <textarea
              className="audit-textarea"
              value={auditNotes}
              onChange={(e) => setAuditNotes(e.target.value)}
              placeholder="可选：补充说明，例如拍摄位置、门店编号等"
              rows={3}
            />
            <button
              className="action-button"
              type="button"
              onClick={handleAuditSubmit}
              disabled={!auditFile || auditLoading || !referenceStatus?.configured}
            >
              {auditLoading ? '审核中...' : '开始审核'}
            </button>
          </div>
        </div>

        {auditError && (
          <div className="audit-error">{auditError}</div>
        )}

        {auditResult && (
          <div className={`audit-result ${auditResult.passed ? 'passed' : 'failed'}`}>
            <div className="audit-result-header">
              <div>
                <div className="audit-result-title">
                  {auditResult.passed ? '审核通过' : '审核不通过'}
                </div>
                <p>{auditResult.summary}</p>
              </div>
              <div className="audit-score">
                <strong>{auditResult.score}</strong>
                <span>/ {auditResult.threshold}</span>
              </div>
            </div>

            {auditResult.annotated_image_base64 && (
              <div className="audit-result-block">
                <h4>问题标记图</h4>
                <img
                  className="annotated-image"
                  src={auditResult.annotated_image_base64}
                  alt="审核问题标记图"
                />
              </div>
            )}

            {auditResult.issues.length > 0 && (
              <div className="audit-result-block">
                <h4>问题点</h4>
                <ul>
                  {auditResult.issues.map((issue, index) => (
                    <li key={`${issue}-${index}`}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            {auditResult.handling_advice && (
              <div className="audit-result-block">
                <h4>处理说明</h4>
                <p className="audit-advice">{auditResult.handling_advice}</p>
              </div>
            )}

            {auditResult.issue_annotations.length > 0 && (
              <div className="audit-result-block">
                <h4>定位说明</h4>
                <ul>
                  {auditResult.issue_annotations.map((issue, index) => (
                    <li key={`${issue.label}-${index}`}>
                      {issue.detail || issue.label}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {auditResult.suggestions.length > 0 && (
              <div className="audit-result-block">
                <h4>建议</h4>
                <ul>
                  {auditResult.suggestions.map((suggestion, index) => (
                    <li key={`${suggestion}-${index}`}>{suggestion}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="audit-result-block">
              <h4>处理说明(JSON)</h4>
              <pre className="audit-json">
                <code>{JSON.stringify(auditResult.handling_advice_json, null, 2)}</code>
              </pre>
            </div>
          </div>
        )}
      </section>

      <div className="messages">
        {messages.length === 0 && !chatLoading && (
          <div className="empty-state">
            <h2>Truverse 电商数据分析助手</h2>
            <p>
              上方可以做桌面清洁审核，下方仍然可以继续通过对话分析 ClickHouse 数据和电商业务问题。
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

        {chatLoading && (
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
            disabled={chatLoading}
          />
          <button type="submit" disabled={chatLoading || !input.trim()}>
            {chatLoading ? '分析中...' : '发送'}
          </button>
        </form>
      </div>
    </div>
  )
}
