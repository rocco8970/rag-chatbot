import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Sidebar from '../components/Sidebar';
import ChatWindow from '../components/ChatWindow';
import { apiService } from '../services/api';
import toast from 'react-hot-toast';

export default function Chat() {
  const [documents, setDocuments] = useState([]);
  const [selectedModel, setSelectedModel] = useState('gemini');
  const [topK, setTopK] = useState(5);
  const [isLoading, setIsLoading] = useState(true);

  // Load existing documents on mount
  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const response = await apiService.listDocuments();
      setDocuments(response.data);
    } catch (error) {
      console.error('Error loading documents:', error);
      toast.error('Could not connect to backend. Make sure FastAPI is running!');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen pt-16 overflow-hidden">
      <Sidebar
        documents={documents}
        setDocuments={setDocuments}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        topK={topK}
        setTopK={setTopK}
      />
      <ChatWindow
        documents={documents}
        selectedModel={selectedModel}
        topK={topK}
      />
    </div>
  );
}