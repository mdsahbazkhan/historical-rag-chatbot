import React, { useState } from 'react'
import Header from '../components/Header.jsx'
import ModeSelector from '../components/ModeSelector.jsx'
import ChatWindow from '../components/ChatWindow.jsx'
import ChatInput from '../components/ChatInput.jsx'
import useChat from '../hooks/useChat.js'

const examples = {
  weather: 'e.g., What was the temperature in Hyderabad on 23 March 2023?',
  stock: 'e.g., What was the stock price of AAPL on 23 March 2023?',
  news: 'e.g., What were the top news headlines on 23 March 2023?'
}

export default function Home() {
  const [mode, setMode] = useState('weather')
  const { messages, loading, handleSendMessage, messagesEndRef } = useChat()

  const onSend = (question) => {
    handleSendMessage(mode, question)
  }

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#111827',
      padding: '20px'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <Header />
        <ModeSelector mode={mode} setMode={setMode} />
        <ChatWindow messages={messages} loading={loading} messagesEndRef={messagesEndRef} />
        <div style={{ textAlign: 'center', marginBottom: '8px', fontSize: '12px', color: '#9ca3af' }}>
          {examples[mode]}
        </div>
        <ChatInput onSend={onSend} loading={loading} />
      </div>
    </div>
  )
}