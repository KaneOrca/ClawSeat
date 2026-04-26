import { useState, useMemo } from 'react';
import { useArena } from '../context/ArenaContext';
import { useLanguage } from '../context/LanguageContext';
import { CHALLENGES } from '../data/mockData';
import { api } from '../api/arena';

/**
 * Shared hook for challenge submission logic across all variants.
 * Encapsulates answer state, submit handler, and challenge lookup.
 */
export function useChallengeSubmission() {
  const {
    currentChallengeId,
    setChallengeId,
    participantCode,
    user,
    login,
    withToast,
    showToast,
    isZenMode
  } = useArena();
  const { t, locale } = useLanguage();

  const [answer, setAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const challenge = useMemo(() => {
    return CHALLENGES.find(c => c.id === currentChallengeId) || CHALLENGES[0];
  }, [currentChallengeId]);

  const handleSubmit = async () => {
    if (!answer.trim() || !participantCode || !currentChallengeId) return;
    setSubmitting(true);
    const data = await withToast<{ correct: boolean; score: number; layer: number; nextHint: string }>(
      () => api.submit(participantCode, currentChallengeId, answer),
      'Submission failed'
    );
    setSubmitting(false);

    if (data && data.correct && user) {
      showToast(t('challengeDetail.status.loading'), 'success');
      const newCompleted = [...new Set([...user.completedChallenges, currentChallengeId])];
      login({ ...user, score: data.score, layer: data.layer, completedChallenges: newCompleted });
    }
  };

  return {
    challenge,
    answer,
    setAnswer,
    submitting,
    handleSubmit,
    currentChallengeId,
    setChallengeId,
    participantCode,
    user,
    isZenMode,
    t,
    locale
  };
}
