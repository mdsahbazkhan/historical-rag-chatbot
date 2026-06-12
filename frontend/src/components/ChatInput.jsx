import React, { useState, useRef, useEffect } from 'react'

export default function ChatInput({ onSend, loading }) {
  const [input, setInput] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [loading])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !loading) {
      onSend(input)
      setInput('')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px' }}>
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type your message..."
        disabled={loading}
        style={{
          flex: 1,
          padding: '12px 16px',
          borderRadius: '24px',
          border: '1px solid #4b5563',
          backgroundColor: '#374151',
          color: '#e5e7eb',
          fontSize: '14px',
          outline: 'none'
        }}
      />
      <button
        type="submit"
        disabled={!input.trim() || loading}
        style={{
          padding: '12px 24px',
          borderRadius: '24px',
          border: 'none',
          backgroundColor: loading || !input.trim() ? '#6b7280' : '#3b82f6',
          color: '#fff',
          fontSize: '14px',
          fontWeight: '500',
          cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
          transition: 'background-color 0.2s'
        }}
      >
        Send
      </button>
    </form>
  )
}