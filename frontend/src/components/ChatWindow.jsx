import React from 'react'
import Message from './Message.jsx'
import Loading from './Loading.jsx'

export default function ChatWindow({ messages, loading, messagesEndRef }) {
  return (
    <div style={{
      height: '500px',
      overflowY: 'auto',
      padding: '20px',
      backgroundColor: '#1f2937',
      borderRadius: '12px',
      boxShadow: '0 2px 10px rgba(0,0,0,0.3)',
      marginBottom: '20px'
    }}>
      {messages.map((msg, index) => (
        <Message key={index} type={msg.type} text={msg.text} />
      ))}
      {loading && <Loading />}
      <div ref={messagesEndRef} />
    </div>
  )
}