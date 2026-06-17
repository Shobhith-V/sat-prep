import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { fetchAttemptedQuestionIds, fetchCompetency } from '../lib/queries';
import { topicStats, weakestTopics, type TopicStat } from '../lib/stats';

interface PracticeProfile {
  loading: boolean;
  seenIds: Set<string>;     // questions already attempted (for unseen counts)
  weakest: TopicStat[];     // top weakest topics (for the adaptive preview)
}

/**
 * Loads the per-student signals Practice Setup needs: which questions have
 * been seen, and the weakest topics to preview for Adaptive mode.
 */
export function usePracticeProfile(): PracticeProfile {
  const { user } = useAuth();
  const [profile, setProfile] = useState<PracticeProfile>({
    loading: true,
    seenIds: new Set(),
    weakest: [],
  });

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    (async () => {
      try {
        const [ids, competency] = await Promise.all([
          fetchAttemptedQuestionIds(user.id),
          fetchCompetency(user.id),
        ]);
        if (cancelled) return;
        setProfile({
          loading: false,
          seenIds: new Set(ids),
          weakest: weakestTopics(topicStats(competency), 3),
        });
      } catch {
        if (!cancelled) setProfile({ loading: false, seenIds: new Set(), weakest: [] });
      }
    })();

    return () => { cancelled = true; };
  }, [user]);

  return profile;
}
