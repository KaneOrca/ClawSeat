import { motion } from 'framer-motion';

export function GeminiOrb() {
  return (
    <div className="gemini-orb-container">
      <motion.div 
        className="gemini-orb-core"
        animate={{
          scale: [1, 1.1, 0.95, 1.05, 1],
          rotate: [0, 180, 360],
          borderRadius: ["40% 60% 70% 30%", "60% 40% 30% 70%", "50% 50% 50% 50%", "40% 60% 70% 30%"]
        }}
        transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div 
        className="gemini-orb-glow"
        animate={{
          scale: [1, 1.2, 0.9, 1.1, 1],
          opacity: [0.6, 0.8, 0.5, 0.7, 0.6]
        }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
