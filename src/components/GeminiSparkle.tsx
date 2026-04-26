import { motion } from 'framer-motion';

export function GeminiSparkle({ size = 48, className = '' }: { size?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      style={{ width: size, height: size, position: 'relative', display: 'inline-block' }}
      animate={{ 
        rotate: [0, 90, 180, 270, 360],
        scale: [1, 1.2, 0.9, 1.15, 1] 
      }}
      transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
    >
      <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="gemini-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#4285f4">
              <animate attributeName="stop-color" values="#4285f4;#9b72cb;#d96570;#4285f4" dur="8s" repeatCount="indefinite" />
            </stop>
            <stop offset="50%" stopColor="#9b72cb">
              <animate attributeName="stop-color" values="#9b72cb;#d96570;#f4b400;#9b72cb" dur="8s" repeatCount="indefinite" />
            </stop>
            <stop offset="100%" stopColor="#f4b400">
              <animate attributeName="stop-color" values="#f4b400;#4285f4;#9b72cb;#f4b400" dur="8s" repeatCount="indefinite" />
            </stop>
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        <path
          d="M50 0 C50 25 75 50 100 50 C75 50 50 75 50 100 C50 75 25 50 0 50 C25 50 50 25 50 0 Z"
          fill="url(#gemini-grad)"
          filter="url(#glow)"
        />
      </svg>
    </motion.div>
  );
}
