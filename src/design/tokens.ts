/**
 * Arena Flagship Design Tokens
 * Gemini x Pretext Edition
 */

export const tokens = {
  colors: {
    base: '#000005',
    aurora: {
      blue: '#4285f4',
      purple: '#9b72cb',
      red: '#d96570',
      yellow: '#f4b400',
      cyan: '#00f0ff'
    },
    text: {
      primary: '#ffffff',
      secondary: 'rgba(255, 255, 255, 0.6)',
      tertiary: 'rgba(255, 255, 255, 0.4)',
      micro: 'rgba(255, 255, 255, 0.2)'
    },
    glass: {
      bg: 'rgba(20, 20, 25, 0.4)',
      border: 'rgba(255, 255, 255, 0.06)',
      highlight: 'rgba(255, 255, 255, 0.15)'
    },
    manuscript: {
      bg: '#fdfcf0',
      ink: '#1a1a1a',
      red: '#b53021',
      dim: '#888',
      faint: '#555',
      muted: '#aaa'
    }
  },
  fonts: {
    display: "'Clash Display', sans-serif",
    body: "'Satoshi', sans-serif",
    mono: "'JetBrains Mono', monospace",
    manuscript: "'Playfair Display', 'Noto Serif SC', serif"
  },
  sizes: {
    xxs: '9px',
    xs: '10px',
    micro: '10px',
    small: '11px',
    sm: '13px',
    md: '14px',
    lg: '17px',
    xl: '18px',
    '2xl': '1.25rem',
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '24px',
    '2xl': '32px',
    '3xl': '48px',
    '4xl': '64px',
  },
  radius: {
    sm: '4px',
    md: '8px',
    lg: '16px',
    xl: '24px',
    full: '9999px',
  },
  shadow: {
    sm: '0 2px 4px rgba(0, 0, 0, 0.2)',
    md: '0 4px 12px rgba(0, 0, 0, 0.3)',
    lg: '0 8px 30px rgba(0, 0, 0, 0.4)',
    glow: (color: string) => `0 0 20px ${color}33, 0 0 40px ${color}1a`,
  },
  zIndex: {
    base: 0,
    content: 2,
    overlay: 10,
    modal: 20,
    toast: 30,
  },
  transitions: {
    /** "Pretext easing" — used throughout the app */
    easing: 'cubic-bezier(0.16, 1, 0.3, 1)',
    default: '0.4s cubic-bezier(0.16, 1, 0.3, 1)',
    slow: '0.8s cubic-bezier(0.16, 1, 0.3, 1)',
    spring: {
      stiff: { type: 'spring', stiffness: 300, damping: 30 },
      soft: { type: 'spring', stiffness: 100, damping: 40 },
      bouncy: { type: 'spring', stiffness: 200, damping: 15 }
    }
  },
  effects: {
    blur: '24px',
    noise: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E\")"
  }
};
