import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../services/api'

export default function useChat() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const addMessage = (type, text) => {
    setMessages(prev => [...prev, { type, text }])
  }

  const handleSendMessage = async (mode, question) => {
    if (!question.trim() || loading) return

    addMessage('user', question)
    setLoading(true)

    try {
      const response = await sendMessage(mode, question)
      const reply = response.answer || response.error || 'Something went wrong.'
      addMessage('bot', reply)
    } catch (error) {
      addMessage('bot', 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return {
    messages,
    loading,
    handleSendMessage,
    messagesEndRef
  }
}