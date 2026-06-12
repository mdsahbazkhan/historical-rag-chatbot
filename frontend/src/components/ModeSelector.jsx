import React from 'react'

export default function ModeSelector({ mode, setMode }) {
  const modes = [
    { value: 'weather', label: '🌦 Weather' },
    { value: 'stock', label: '📈 Stock' },
    { value: 'news', label: '📰 News' }
  ]

  return (
    <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap', justifyContent: 'center' }}>
      {modes.map(m => (
        <button
          key={m.value}
          onClick={() => setMode(m.value)}
          style={{
            padding: '10px 20px',
            borderRadius: '20px',
            border: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            backgroundColor: mode === m.value ? '#3b82f6' : '#374151',
            color: mode === m.value ? '#fff' : '#e5e7eb',
            transition: 'all 0.2s'
          }}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}