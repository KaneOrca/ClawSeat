import React from 'react';
import type { VariantType } from '../context/ArenaContext';


// V2
import { HomeView as V2Home } from './v2/views/HomeView';
import { ChallengeDetailView as V2ChallengeDetail } from './v2/views/ChallengeDetailView';
import { WatchView as V2Watch } from './v2/views/WatchView';
import { HallViewV2 } from '../views/Hall/v2/HallView';
import { CommunityViewV2 } from '../views/Community/v2/CommunityView';

// V3
import { HomeViewV3 as V3Home } from '../views/Home/v3/HomeViewV3';
import { ChallengeDetailV3 as V3ChallengeDetail } from '../views/ChallengeDetail/v3/ChallengeDetailV3';
import { WatchViewV3 as V3Watch } from '../views/Watch/v3/WatchViewV3';
import { HallViewV3 } from '../views/Hall/v3/HallView';
import { CommunityViewV3 } from '../views/Community/v3/CommunityView';

type VariantViews = {
  home: React.FC;
  challengeDetail: React.FC;
  watch: React.FC;
  hall: React.FC;
  community: React.FC;
};

export const variantRegistry: Record<VariantType, VariantViews> = {
  v2: { home: V2Home, challengeDetail: V2ChallengeDetail, watch: V2Watch, hall: HallViewV2, community: CommunityViewV2 },
  v3: { home: V3Home, challengeDetail: V3ChallengeDetail, watch: V3Watch, hall: HallViewV3, community: CommunityViewV3 },
};
