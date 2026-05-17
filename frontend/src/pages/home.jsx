import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  FiUpload, FiMessageSquare, FiShield, 
  FiBarChart2, FiBook, FiArrowRight, FiStar 
} from 'react-icons/fi';
import { BsRobot, BsLightningChargeFill } from 'react-icons/bs';
import { FaBrain } from 'react-icons/fa';

const FeatureCard = ({ icon, title, description, delay }) => (
  <motion.div
    initial={{ opacity: 0, y: 30 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.5 }}
    className="card group cursor-pointer"
  >
    <div className="flex items-center gap-4 mb-4">
      <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 
                      border border-blue-500/30 group-hover:from-blue-500/30 
                      group-hover:to-purple-500/30 transition-all duration-300">
        <span className="text-2xl text-blue-400">{icon}</span>
      </div>
      <h3 className="text-lg font-semibold text-white">{title}</h3>
    </div>
    <p className="text-gray-400 text-sm leading-relaxed">{description}</p>
  </motion.div>
);

const StatCard = ({ number, label, delay }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.8 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ delay, duration: 0.5 }}
    className="text-center"
  >
    <div className="text-4xl font-bold gradient-text mb-2">{number}</div>
    <div className="text-gray-400 text-sm">{label}</div>
  </motion.div>
);

export default function Home() {
  const features = [
    {
      icon: <FiUpload />,
      title: "Multi-Format Upload",
      description: "Upload PDF, DOCX, TXT, CSV files. Our system processes any document format intelligently.",
      delay: 0.2
    },
    {
      icon: <FaBrain />,
      title: "Smart RAG Pipeline",
      description: "Advanced Retrieval-Augmented Generation ensures accurate, context-aware responses.",
      delay: 0.3
    },
    {
      icon: <BsLightningChargeFill />,
      title: "Lightning Fast",
      description: "Powered by Groq's ultra-fast inference. Get answers in milliseconds.",
      delay: 0.4
    },
    {
      icon: <FiShield />,
      title: "Source Attribution",
      description: "Every answer includes exact source references and confidence scores.",
      delay: 0.5
    },
    {
      icon: <FiBarChart2 />,
      title: "Analytics Dashboard",
      description: "Track usage patterns and performance metrics in real-time.",
      delay: 0.6
    },
    {
      icon: <FiBook />,
      title: "Multi-Model Support",
      description: "Switch between Gemini 2.5 and Groq Llama 3.1 for different needs.",
      delay: 0.7
    },
  ];

  return (
    <div className="min-h-screen pt-20">
      {/* Hero Section */}
      <div className="relative overflow-hidden px-6 py-20 text-center">
        {/* Glow effects */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 
                        w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/3 left-1/3 -translate-x-1/2 -translate-y-1/2 
                        w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full 
                     bg-blue-500/10 border border-blue-500/30 text-blue-400 
                     text-sm font-medium mb-8 relative z-10"
        >
          <FiStar className="text-yellow-400" />
          Final Year Project — Jamia Hamdard 2024-25
          <FiStar className="text-yellow-400" />
        </motion.div>

        {/* Main Heading */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="text-5xl md:text-7xl font-extrabold text-white mb-6 leading-tight relative z-10"
        >
          Chat With Your
          <br />
          <span className="gradient-text">Documents</span>
          <br />
          Using AI
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-12 leading-relaxed relative z-10"
        >
          Upload any document and ask questions in natural language. 
          Powered by RAG for 
          <span className="text-blue-400 font-semibold"> accurate, source-backed answers</span>.
        </motion.p>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="flex flex-col sm:flex-row gap-4 justify-center mb-20 relative z-10"
        >
          <Link to="/chat">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="btn-primary flex items-center gap-2 px-8 py-4 text-lg"
            >
              <BsRobot />
              Start Chatting
              <FiArrowRight />
            </motion.button>
          </Link>
          <Link to="/dashboard">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="btn-secondary flex items-center gap-2 px-8 py-4 text-lg"
            >
              <FiBarChart2 />
              View Dashboard
            </motion.button>
          </Link>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto"
        >
          <StatCard number="5+" label="File Formats" delay={0.5} />
          <StatCard number="2" label="AI Models" delay={0.6} />
          <StatCard number="<1s" label="Response Time" delay={0.7} />
          <StatCard number="100%" label="Free to Use" delay={0.8} />
        </motion.div>
      </div>

      {/* Features Section */}
      <div className="px-6 py-16 max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center mb-12"
        >
          <h2 className="text-4xl font-bold text-white mb-4">
            Everything You <span className="gradient-text">Need</span>
          </h2>
          <p className="text-gray-400 text-lg">
            A complete AI document assistant
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <FeatureCard key={index} {...feature} />
          ))}
        </div>
      </div>

      {/* Footer */}
      <footer className="text-center py-12 text-gray-500 border-t border-white/10 mt-12">
        <p className="mb-2">
          Built with ❤️ by <span className="gradient-text font-semibold">Your Name</span>
        </p>
        <p className="text-sm mb-4">
          Jamia Hamdard • Department of Computer Science • 2024-25
        </p>
        <div className="flex justify-center gap-2 flex-wrap">
          <span className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-400 text-xs">React</span>
          <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-400 text-xs">FastAPI</span>
          <span className="px-3 py-1 rounded-full bg-green-500/20 text-green-400 text-xs">ChromaDB</span>
          <span className="px-3 py-1 rounded-full bg-yellow-500/20 text-yellow-400 text-xs">Gemini 2.5</span>
          <span className="px-3 py-1 rounded-full bg-pink-500/20 text-pink-400 text-xs">Groq Llama</span>
        </div>
      </footer>
    </div>
  );
}