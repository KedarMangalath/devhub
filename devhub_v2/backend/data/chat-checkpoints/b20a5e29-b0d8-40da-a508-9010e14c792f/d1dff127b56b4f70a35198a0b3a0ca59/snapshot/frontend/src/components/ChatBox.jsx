import { useState } from 'react'
import { Send } from 'lucide-react'

export default function ChatBox({ messages = [], onSendMessage }) {
  const [inputValue, setInputValue] = useState('')

  const handleSend = (e) => {
    e.preventDefault()
    if (inputValue.trim()) {
      onSendMessage(inputValue.trim())
      setInputValue('')
    }
  }

  return (
    <div className="flex flex-col h-full bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">Consultation Chat</h3>
        <span className="flex h-2 w-2 rounded-full bg-green-500"></span>
      </div>

      {/* Messages Area */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-gray-50/30 min-h-[300px]">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-gray-400 text-sm">
            <p>No messages yet.<br/>Send a message to start the conversation.</p>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isMe = msg.isSelf || msg.sender === 'me'
            return (
              <div
                key={msg.id || idx}
                className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm ${
                    isMe
                      ? 'bg-blue-600 text-white rounded-br-sm'
                      : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
                  }`}
                >
                  {msg.text}
                </div>
                <span className="text-[10px] text-gray-400 mt-1 mx-1 font-medium">
                  {msg.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            )
          })
        )}
      </div>

      {/* Input Area */}
      <form 
        onSubmit={handleSend} 
        className="p-3 bg-white border-t border-gray-200 flex items-center gap-2"
      >
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type your message..."
          className="flex-1 px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
        />
        <button
          type="submit"
          disabled={!inputValue.trim()}
          className="p-2.5 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          aria-label="Send message"
        >
          <Send className="w-4 h-4 ml-0.5" />
        </button>
      </form>
    </div>
  )
}