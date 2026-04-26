import React from 'react';

interface PoeticStatusLineProps {
  status: 'loading' | 'empty' | 'error';
  message: string;
  className?: string;
}

export const PoeticStatusLine: React.FC<PoeticStatusLineProps> = ({ 
  status, 
  message, 
  className = '' 
}) => {
  const getIndicator = () => {
    switch (status) {
      case 'loading': return <span className="animate-pulse inline-block mr-2">∿</span>;
      case 'empty': return <span className="opacity-50 inline-block mr-2">○</span>;
      case 'error': return <span className="text-red-500 inline-block mr-2">×</span>;
    }
  };

  return (
    <div className={`font-mono text-sm text-gray-500 dark:text-gray-400 flex items-center ${className}`}>
      {getIndicator()}
      <span className="tracking-widest lowercase">{message}</span>
    </div>
  );
};
