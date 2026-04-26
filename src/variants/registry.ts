import React from 'react';
import type { VariantType } from '../context/ArenaContext';


// V2
import { HomeView as V2Home } from './v2/views/HomeView';
import { ChallengeDetailView as V2ChallengeDetail } from './v2/views/ChallengeDetailView';
import { WatchView as V2Watch } from './v2/views/WatchView';

// V3
import { HomeViewV3 as V3Home } from '../views/Home/v3/HomeViewV3';
import { ChallengeDetailV3 as V3ChallengeDetail } from '../views/ChallengeDetail/v3/ChallengeDetailV3';
import { WatchViewV3 as V3Watch } from '../views/Watch/v3/WatchViewV3';

type VariantViews = {
  home: React.FC;
  challengeDetail: React.FC;
  watch: React.FC;
};

export const variantRegistry: Record<VariantType, VariantViews> = {
    v2: { home: V2Home, challengeDetail: V2ChallengeDetail, watch: V2Watch },
  v3: { home: V3Home, challengeDetail: V3ChallengeDetail, watch: V3Watch },
};
