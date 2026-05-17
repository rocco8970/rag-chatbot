import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { FiCopy, FiCheck, FiChevronDown, FiChevronUp } from 'react-icons/fi';
import { BsRobot } from 'react-icons/bs';
import toast from 'react-hot-toast';

export default function Message({ message }) {
  const [copied, setCopied] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const isBot = message.role === 'bot';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    toast.success('Copied!');
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTime = (date) => {
    return new Date(date).toLocaleTimeString([], { 
      hour: '2-digit', minute: '2-digit' 
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3 }}
      className={`flex gap-3 ${isBot ? 'flex-row' : 'flex-row-reverse'}`}
    >
      {/* Avatar */}
      <div className={`
        w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center
        ${isBot 
          ? 'bg-gradient-to-br from-blue-500 to-purple-600' 
          : 'bg-gradient-to-br from-green-400 to-blue-500'}
      `}>
        {isBot ? (
          <BsRobot className="text-white text-sm" />
        ) : (
          <span className="text-white text-sm font-bold">U</span>
        )}
      </div>

      {/* Message Content */}
      <div className={`max-w-2xl ${isBot ? '' : 'items-end'} flex flex-col gap-1`}>
        <div className={`
          relative group px-5 py-4 rounded-2xl
          ${isBot 
            ? 'glass border-white/10 rounded-tl-sm' 
            : 'bg-gradient-to-br from-blue-500 to-blue-600 rounded-tr-sm shadow-lg shadow-blue-500/20'
          }
        `}>
          {/* Copy button */}
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 
                       transition-opacity p-1.5 rounded-lg bg-white/10 hover:bg-white/20"
          >
            {copied ? (
              <FiCheck className="text-green-400 text-xs" />
            ) : (
              <FiCopy className="text-gray-300 text-xs" />
            )}
          </button>

          {/* Message Text */}
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              components={{
                p: ({children}) => <p className="text-gray-200 mb-2 last:mb-0">{children}</p>,
                ul: ({children}) => <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>,
                ol: ({children}) => <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>,
                li: ({children}) => <li className="text-gray-300">{children}</li>,
                strong: ({children}) => <strong className="text-white font-semibold">{children}</strong>,
                code: ({children}) => (
                  <code className="bg-black/30 px-1.5 py-0.5 rounded text-blue-300 text-xs">
                    {children}
                  </code>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Sources Section */}
          {isBot && message.sources && message.sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/10">
              <button
                onClick={() => setShowSources(!showSources)}
                className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300"
              >
                {showSources ? <FiChevronUp /> : <FiChevronDown />}
                {showSources ? 'Hide' : 'View'} {message.sources.length} source{message.sources.length > 1 ? 's' : ''}
              </button>

              <AnimatePresence>
                {showSources && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="mt-2 space-y-2 overflow-hidden"
                  >
                    {message.sources.map((source, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-white/5 border border-white/10">
                        <span className="text-blue-400 text-xs font-mono font-bold 
                                        bg-blue-500/20 px-1.5 py-0.5 rounded">
                          {i + 1}
                        </span>
                        <div className="flex-1">
                          <p className="text-gray-300 text-xs">{source.source}</p>
                          <p className="text-gray-500 text-xs">Chunk #{source.chunk_index}</p>
                        </div>
                      </div>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span className="text-gray-500 text-xs px-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </motion.div>
  );
}