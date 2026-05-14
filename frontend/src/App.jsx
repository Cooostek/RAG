import { useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

function App() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [topK, setTopK] = useState(5)
  const [alpha, setAlpha] = useState(0.6)

  // NEW: переключатель LLM
  const [useLLM, setUseLLM] = useState(true)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    setAnswer('')
    setSources([])

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          top_k: topK,
          alpha,
          use_llm: useLLM // NEW
        })
      })

      const data = await response.json()

      if (!response.ok || data.error) {
        setAnswer(`Ошибка: ${data.error || response.status}`)
      } else {
        setAnswer(data.answer || 'Ответ не сгенерирован')
        setSources(Array.isArray(data.sources) ? data.sources : [])
      }
    } catch (err) {
      setAnswer('Ошибка соединения с сервером')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-container">
      <h1>RAG AI-помощник</h1>

      <form onSubmit={handleSubmit} className="input-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Введите ваш вопрос..."
          disabled={loading}
        />

        <div className="controls">
          <label>
            top_k:
            <input
              type="number"
              min="1"
              max="10"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              disabled={loading}
            />
          </label>

          <label>
            alpha:
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              value={alpha}
              onChange={(e) => setAlpha(Number(e.target.value))}
              disabled={loading}
            />
          </label>

          {/* NEW: toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={useLLM}
              onChange={(e) => setUseLLM(e.target.checked)}
              disabled={loading}
            />
            Ответ с Ollama
          </label>
        </div>

        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? 'Загрузка...' : 'Отправить'}
        </button>

        {/* NEW: маленькая подсказка */}
        <div style={{ marginTop: 10, fontSize: 12, opacity: 0.8 }}>
          Режим: <b>{useLLM ? 'с генерацией (Ollama)' : 'только поиск (без LLM)'}</b>
        </div>
      </form>

      {answer && (
        <div className="card">
          <h2>Ответ</h2>
          <p>{answer}</p>
        </div>
      )}

      {sources.length > 0 && (
        <div className="card">
          <h2>Источники</h2>
          {sources.map((s, idx) => (
            <div key={idx} className="source-item">
              <div className="source-meta">
                <span>score: {s.score}</span>
                <span>type: {s.type}</span>
              </div>
              {s.metadata?.page_title && (
                <div>
                  <b>Раздел:</b> {s.metadata.page_title}
                </div>
              )}
              {s.metadata?.source_url && (
                <div>
                  <b>URL:</b>{' '}
                  <a href={s.metadata.source_url} target="_blank" rel="noreferrer">
                    {s.metadata.source_url}
                  </a>
                </div>
              )}
              <pre>{s.text}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default App