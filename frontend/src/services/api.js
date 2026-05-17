import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data?.detail || error.message);
    return Promise.reject(error);
  }
);

// API Functions
export const apiService = {
  // Health check
  health: () => api.get('/health'),
  
  // Stats
  getStats: () => api.get('/stats'),
  
  // Documents
  uploadDocument: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  
  listDocuments: () => api.get('/documents'),
  
  deleteDocument: (docId) => api.delete(`/documents/${docId}`),
  
  clearAllDocuments: () => api.delete('/documents'),
  
  // Chat
  sendMessage: (question, model = 'gemini', topK = 5) => 
    api.post('/chat', { question, model, top_k: topK }),
  
  getChatHistory: () => api.get('/chat/history'),
  
  clearChatHistory: () => api.delete('/chat/history'),
};

export default api;