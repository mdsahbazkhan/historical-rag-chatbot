import React from 'react'

export default function Loading() {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'flex-start',
      marginBottom: '12px'
    }}>
      <div style={{
        maxWidth: '70%',
        padding: '12px 16px',
        borderRadius: '18px',
        backgroundColor: '#4b5563',
        color: '#9ca3af',
        fontSize: '14px',
        fontStyle: 'italic'
      }}>
        Thinking...
      </div>
    </div>
  )
}