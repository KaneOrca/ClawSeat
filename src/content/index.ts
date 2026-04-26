import { contentEn } from './en';
import { contentZh } from './zh-CN';

export type Language = 'en' | 'zh-CN';

export const getContent = (lang: Language) => {
  return lang === 'en' ? contentEn : contentZh;
};
