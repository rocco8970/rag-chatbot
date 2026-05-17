import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import { 
  FiUploadCloud, FiFile, FiTrash2, 
  FiFileText, FiSettings 
} from 'react-icons/fi';
import { apiService } from '../services/api';
import toast from 'react-hot-toast';

export default function Sidebar({ 
  documents, 
  setDocuments, 
  selectedModel, 
  setSelectedModel,
  topK,
  setTopK
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const onDrop = async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    
    setUploading(true);
    
    for (const file of acceptedFiles) {
      try {
        setUploadProgress(0);
        toast.loading(`Uploading ${file.name}...`, { id: file.name });
        
        const response = await apiService.uploadDocument(file);
        
        setDocuments(prev => [...prev, response.data.document]);
        toast.success(`✅ ${file.name} uploaded!`, { id: file.name });
      } catch (error) {
        toast.error(`❌ Failed: ${error.response?.data?.detail || error.message}`, { id: file.name });
      }
    }
    
    setUploading(false);
    setUploadProgress(0);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/markdown': ['.md'],
      'text/csv': ['.csv'],
    },
    multiple: true,
  });

  const handleDelete = async (docId, name) => {
    try {
      await apiService.deleteDocument(docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
      toast.success(`Deleted ${name}`);
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const handleClearAll = async () => {
    if (!confirm('Clear ALL documents?')) return;
    try {
      await apiService.clearAllDocuments();
      setDocuments([]);
      toast.success('All documents cleared');
    } catch (error) {
      toast.error('Failed to clear');
    }
  };

  return (
    <motion.aside
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="w-80 h-full glass-strong border-r border-white/10 flex flex-col overflow-hidden"
    >
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <h2 className="text-white font-semibold flex items-center gap-2">
          <FiFileText className="text-blue-400" />
          Document Manager
        </h2>
      </div>

      {/* Upload Zone */}
      <div className="p-4 border-b border-white/10">
        <div
          {...getRootProps()}
          className={`
            border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer
            transition-all duration-300
            ${isDragActive 
              ? 'border-blue-400 bg-blue-500/10 scale-105' 
              : 'border-white/20 hover:border-blue-400/50 hover:bg-white/5'
            }
          `}
        >
          <input {...getInputProps()} />
          
          <motion.div
            animate={{ y: isDragActive ? -5 : 0 }}
            className="flex flex-col items-center gap-3"
          >
            <div className={`
              w-12 h-12 rounded-2xl flex items-center justify-center
              ${isDragActive 
                ? 'bg-blue-500 text-white' 
                : 'bg-white/10 text-gray-400'
              }
            `}>
              <FiUploadCloud className="text-2xl" />
            </div>
            
            <div>
              <p className="text-white text-sm font-medium">
                {isDragActive ? 'Drop here!' : 'Upload Documents'}
              </p>
              <p className="text-gray-500 text-xs mt-1">
                PDF, DOCX, TXT, MD, CSV
              </p>
            </div>
          </motion.div>
        </div>

        {uploading && (
          <div className="mt-3">
            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: '0%' }}
                animate={{ width: '100%' }}
                transition={{ duration: 2 }}
                className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* Documents List */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-gray-400 text-xs font-semibold uppercase">
            Loaded ({documents.length})
          </h3>
          {documents.length > 0 && (
            <button
              onClick={handleClearAll}
              className="text-red-400 hover:text-red-300 text-xs"
            >
              Clear All
            </button>
          )}
        </div>

        {documents.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            <FiFile className="mx-auto text-3xl mb-2 opacity-50" />
            No documents yet
          </div>
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {documents.map((doc) => (
                <motion.div
                  key={doc.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="glass p-3 rounded-xl group hover:bg-white/10 transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <FiFile className="text-blue-400 flex-shrink-0" />
                        <p className="text-white text-sm font-medium truncate">
                          {doc.name}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">
                          {doc.format?.toUpperCase()}
                        </span>
                        <span>{doc.chunks} chunks</span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(doc.id, doc.name)}
                      className="text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <FiTrash2 className="text-sm" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Settings */}
      <div className="p-4 border-t border-white/10 space-y-3">
        <div>
          <label className="text-xs text-gray-400 mb-2 block flex items-center gap-2">
            <FiSettings />
            AI Model
          </label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="input-field text-sm cursor-pointer"
          >
            <option value="gemini">⚡ Gemini 2.5 Flash</option>
            <option value="groq">🚀 Groq Llama 3.1</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-gray-400 mb-2 block">
            Context Chunks: <span className="text-blue-400 font-semibold">{topK}</span>
          </label>
          <input
            type="range"
            min="1"
            max="10"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="w-full accent-blue-500"
          />
        </div>
      </div>
    </motion.aside>
  );
}