import React from 'react';
import { ArenaProvider, useArena } from './context/ArenaContext';
import { LanguageProvider } from './context/LanguageContext';
import { PhysicsProvider } from './context/PhysicsContext';
import { MainLayout } from './layouts/MainLayout';
import { variantRegistry } from './variants/registry';

// Shared Views (not variant-specific)
import { HallView } from './views/Hall/HallView';
import { CommunityView } from './views/Community/CommunityView';

import './index.css';

/**
 * Router component handles conditional view rendering based on ArenaContext.
 */
const Router: React.FC = () => {
  const { currentView, currentChallengeId, variant } = useArena();
  const views = variantRegistry[variant];

  // Challenge Detail takes priority if an ID is set
  if (currentChallengeId !== null) {
    const ChallengeDetail = views.challengeDetail;
    return <ChallengeDetail />;
  }

  switch (currentView) {
    case 'home': {
      const Home = views.home;
      return <Home />;
    }
    case 'hall':
    case 'challenges':
      return <HallView />;
    case 'watch': {
      const Watch = views.watch;
      return <Watch />;
    }
    case 'community':
      return <CommunityView />;
    default: {
      const Home = views.home;
      return <Home />;
    }
  }
};

/**
 * App entry point wraps the application in the state provider and main layout.
 */
function App() {
  return (
    <LanguageProvider>
      <ArenaProvider>
        <PhysicsProvider>
          <MainLayout>
            <Router />
          </MainLayout>
        </PhysicsProvider>
      </ArenaProvider>
    </LanguageProvider>
  );
}

export default App;
