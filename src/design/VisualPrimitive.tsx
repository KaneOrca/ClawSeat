import React from 'react';
import { motion } from 'framer-motion';
import { tokens } from './tokens';

export const FlagshipCard: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ 
  children, 
  style
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      style={{
        ...style,
        background: 'none',
        border: 'none',
        position: 'relative',
        padding: '1.5rem 0'
      }}
    >
      <div style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </div>
    </motion.div>
  );
};

export const NeuralBadge: React.FC<{ text: string; color?: string }> = ({ text, color = tokens.colors.aurora.blue }) => {
  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '8px',
      padding: '4px 12px',
      borderRadius: '100px',
      background: `${color}15`,
      border: `1px solid ${color}30`,
      color: color,
      fontFamily: tokens.fonts.mono,
      fontSize: '10px',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.1em'
    }}>
      <div className="pulse-dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: color }} />
      {text}
    </div>
  );
};

export const NeuralLoading: React.FC<{ label?: string }> = ({ label = 'SYNCHRONIZING_RIFT' }) => {
  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center', 
      padding: '4rem',
      gap: '2rem'
    }}>
      <div style={{ position: 'relative', width: '60px', height: '60px' }}>
        {[0, 1, 2].map(i => (
          <motion.div
            key={i}
            animate={{ 
              rotate: 360,
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.6, 0.3]
            }}
            transition={{ 
              duration: 3, 
              repeat: Infinity, 
              delay: i * 0.4,
              ease: "easeInOut"
            }}
            style={{
              position: 'absolute',
              inset: 0,
              border: `2px solid ${i === 0 ? tokens.colors.aurora.blue : i === 1 ? tokens.colors.aurora.cyan : tokens.colors.aurora.purple}`,
              borderRadius: i === 0 ? '40%' : i === 1 ? '50%' : '60%',
            }}
          />
        ))}
      </div>
      <div data-functional-text="true" style={{ 
        fontFamily: tokens.fonts.mono, 
        fontSize: '11px', 
        color: tokens.colors.text.tertiary,
        letterSpacing: '0.2em'
      }}>
        [ {label}... ]
      </div>
    </div>
  );
};

export const NeuralEmpty: React.FC<{ label?: string; sublabel?: string }> = ({ 
  label = 'NO_SIGNAL_DETECTED',
  sublabel = 'The neural rift is currently silent at this vector.'
}) => {
  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center', 
      padding: '6rem 2rem',
      textAlign: 'center',
      gap: '1.5rem'
    }}>
      <div style={{ 
        width: '1px', 
        height: '60px', 
        background: `linear-gradient(to bottom, transparent, ${tokens.colors.glass.border}, transparent)` 
      }} />
      <div>
        <div data-functional-text="true" style={{ 
          fontFamily: tokens.fonts.mono, 
          fontSize: '12px', 
          color: tokens.colors.aurora.red,
          letterSpacing: '0.2em',
          marginBottom: '0.5rem'
        }}>
          // {label}
        </div>
        <div data-functional-text="true" style={{ 
          fontSize: '1rem', 
          color: tokens.colors.text.secondary,
          maxWidth: '400px'
        }}>
          {sublabel}
        </div>
      </div>
      <div style={{ 
        width: '1px', 
        height: '60px', 
        background: `linear-gradient(to bottom, transparent, ${tokens.colors.glass.border}, transparent)` 
      }} />
    </div>
  );
};
