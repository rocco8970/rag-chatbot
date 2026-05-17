import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiSend, FiTrash2 } from 'react-icons/fi';
import { BsRobot } from 'react-icons/bs';
import Message from './Message';
import { apiService } from '../services/api';
import toast from 'react-hot-toast';

export default function ChatWindow({ documents, selectedModel, topK }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'bot',
      content: "Hello! 👋 I'm your AI document assistant. Upload documents from the sidebar and ask me anything!",
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    if (documents.length === 0) {
      toast.error('Please upload a document first!');
      return;
    }

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await apiService.sendMessage(input.trim(), selectedModel, topK);
      
      const botMessage = {
        id: Date.now() + 1,
        role: 'bot',
        content: response.data.answer,
        sources: response.data.sources,
        model: response.data.model_used,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      toast.error('Failed to get response');
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'bot',
        content: `❌ Error: ${error.response?.data?.detail || error.message}`,
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    setMessages([{
      id: 1,
      role: 'bot',
      content: "Chat cleared! Ready for new questions.",
      timestamp: new Date(),
    }]);
    toast.success('Chat cleared!');
  };

  const suggestions = [
    "Summarize this document",
    "What are the key points?",
    "Explain the main concepts",
  ];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Chat Header */}
      <div className="glass-strong border-b border-white/10 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 
                          flex items-center justify-center shadow-lg shadow-blue-500/30">
            <BsRobot className="text-white text-sm" />
          </div>
          <div>
            <h3 className="text-white font-medium text-sm">RAG Assistant</h3>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="text-green-400 text-xs">Online</span>
              <span className="text-gray-500 text-xs">•</span>
              <span className="text-blue-400 text-xs">{selectedModel.toUpperCase()}</span>
            </div>
          </div>
          {documents.length > 0 && (
            <span className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-400 text-xs">
              📄 {documents.length} doc{documents.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
        
        <button
          onClick={handleClearChat}
          className="btn-secondary text-sm flex items-center gap-2"
          title="Clear chat"
        >
          <FiTrash2 />
          Clear
        </button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        <AnimatePresence>
          {messages.map((message) => (
            <Message key={message.id} message={message} />
          ))}
        </AnimatePresence>

        {/* Typing Indicator */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 
                            flex items-center justify-center">
              <BsRobot className="text-white text-sm" />
            </div>
            <div className="glass px-5 py-4 rounded-2xl rounded-tl-sm">
              <div className="flex items-center gap-1">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
                <span className="text-gray-400 text-xs ml-2">AI is thinking...</span>
              </div>
            </div>
          </motion.div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Suggestions */}
      {messages.length === 1 && documents.length > 0 && (
        <div className="px-6 py-2">
          <p className="text-gray-500 text-xs mb-2">💡 Try asking:</p>
          <div className="flex gap-2 flex-wrap">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => setInput(s)}
                className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 
                           text-gray-400 text-xs hover:bg-white/10 hover:text-white 
                           transition-all duration-200"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="glass-strong border-t border-white/10 p-4">
        <div className="flex gap-3 items-end max-w-4xl mx-auto">
          <div className="flex-1">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                documents.length === 0 
                  ? "Upload a document first..." 
                  : "Ask anything about your documents..."
              }
              disabled={documents.length === 0}
              rows={1}
              className="input-field resize-none max-h-32"
              style={{ minHeight: '48px' }}
            />
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleSend}
            disabled={!input.trim() || isLoading || documents.length === 0}
            className="btn-primary p-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <FiSend className="text-lg" />
          </motion.button>
        </div>
      </div>
    </div>
  );
}