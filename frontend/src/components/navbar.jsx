import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FiHome, FiMessageSquare, FiBarChart2 } from 'react-icons/fi';
import { BsRobot } from 'react-icons/bs';

export default function Navbar() {
  const location = useLocation();

  const navLinks = [
    { to: '/', label: 'Home', icon: <FiHome /> },
    { to: '/chat', label: 'Chat', icon: <FiMessageSquare /> },
    { to: '/dashboard', label: 'Dashboard', icon: <FiBarChart2 /> },
  ];

  return (
    <motion.nav
      initial={{ y: -60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="fixed top-0 left-0 right-0 z-50 glass-strong border-b border-white/10 px-6 py-3"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 
                          flex items-center justify-center shadow-lg shadow-blue-500/30">
            <BsRobot className="text-white text-xl" />
          </div>
          <div>
            <span className="text-white font-bold text-lg">RAG</span>
            <span className="gradient-text font-bold text-lg">Chat</span>
          </div>
        </Link>

        {/* Nav Links */}
        <div className="hidden md:flex items-center gap-2">
          {navLinks.map((link) => (
            <Link key={link.to} to={link.to}>
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                           transition-all duration-200
                           ${location.pathname === link.to
                             ? 'bg-white/15 text-white border border-white/20'
                             : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
              >
                {link.icon}
                {link.label}
              </motion.div>
            </Link>
          ))}
        </div>

        {/* CTA */}
        <Link to="/chat">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="btn-primary text-sm flex items-center gap-2"
          >
            <FiMessageSquare />
            Start Chat
          </motion.button>
        </Link>
      </div>
    </motion.nav>
  );
}