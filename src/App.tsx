import React from 'react';
import { ArenaProvider, useArena } from './context/ArenaContext';
import { LanguageProvider } from './context/LanguageContext';
import { PhysicsProvider } from './context/PhysicsContext';
import { MainLayout } from './layouts/MainLayout';
import { variantRegistry } from './variants/registry';

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
    case 'auth': {
      const Auth = views.auth;
      return <Auth />;
    }
    case 'hall':
    case 'challenges': {
      const Hall = views.hall;
      return <Hall />;
    }
    case 'watch': {
      const Watch = views.watch;
      return <Watch />;
    }
    case 'community': {
      const Community = views.community;
      return <Community />;
    }
    default: {
      const Home = views.home;
      return <Home />;
    }
  }
};

const AppContent: React.FC = () => {
  return (
    <MainLayout>
      <Router />
    </MainLayout>
  );
};

/**
 * App entry point wraps the application in the state provider and main layout.
 */
function App() {
  return (
    <LanguageProvider>
      <ArenaProvider>
        <PhysicsProvider>
          <AppContent />
        </PhysicsProvider>
      </ArenaProvider>
    </LanguageProvider>
  );
}

export default App;
