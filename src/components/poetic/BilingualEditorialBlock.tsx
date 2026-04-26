import React from 'react';
import { getContent } from '../../content';
import type { Language } from '../../content';

interface BilingualEditorialBlockProps {
  lang: Language;
  section: 'home' | 'challengeDetail' | 'watch';
  className?: string;
}

export const BilingualEditorialBlock: React.FC<BilingualEditorialBlockProps> = ({ 
  lang, 
  section, 
  className = '' 
}) => {
  const content = getContent(lang)[section];
  
  return (
    <article className={`max-w-prose mx-auto space-y-6 ${className}`}>
      <header className="space-y-2 border-b border-gray-200 pb-4 dark:border-gray-800">
        <h1 className="text-4xl font-serif tracking-tight">{content.title}</h1>
        <p className="text-lg italic text-gray-500 dark:text-gray-400">{content.subtitle}</p>
      </header>
      
      <div className="text-base leading-relaxed text-gray-800 dark:text-gray-300 font-serif">
        {section === 'home' && (content as any).manifesto}
        {(section === 'challengeDetail' || section === 'watch') && (content as any).body}
      </div>
      
      <div className="pt-6">
        <button className="px-6 py-2 border border-black dark:border-white uppercase text-sm tracking-widest hover:bg-black hover:text-white dark:hover:bg-white dark:hover:text-black transition-colors">
          {content.cta}
        </button>
      </div>
    </article>
  );
};
