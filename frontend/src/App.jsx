import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Chat from './pages/Chat';

function App() {
  return (
    <Router>
      <div className="animated-bg min-h-screen">
        <Navbar />
        
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route 
            path="/dashboard" 
            element={
              <div className="pt-20 text-center text-white min-h-screen flex items-center justify-center">
                <div>
                  <h1 className="text-5xl font-bold gradient-text mb-4">Dashboard</h1>
                  <p className="text-gray-400">Coming next! 📊</p>
                </div>
              </div>
            } 
          />
        </Routes>

        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: 'rgba(15, 12, 41, 0.9)',
              backdropFilter: 'blur(10px)',
              color: '#fff',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '12px',
            },
          }}
        />
      </div>
    </Router>
  );
}

export default App;