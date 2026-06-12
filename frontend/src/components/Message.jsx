import React from 'react'

export default function Message({ type, text }) {
  const isUser = type === 'user'

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '12px'
    }}>
      <div style={{
        maxWidth: '70%',
        padding: '12px 16px',
        borderRadius: '18px',
        backgroundColor: isUser ? '#4b5563' : '#3b82f6',
        color: '#fff',
        fontSize: '14px',
        lineHeight: '1.5'
      }}>
        {text}
      </div>
    </div>
  )
}