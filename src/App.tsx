import React, { useEffect } from 'react';
import { ArenaProvider, useArena } from './context/ArenaContext';
import { LanguageProvider } from './context/LanguageContext';
import { PhysicsProvider } from './context/PhysicsContext';
import { MainLayout } from './layouts/MainLayout';
import { variantRegistry } from './variants/registry';
import { useFunctionalTextHover } from './hooks/useFunctionalTextHover';
import { WatchViewV3Flow } from './views/Watch/v3/WatchViewV3Flow';
import { tokens } from './design/tokens';

import './index.css';
import './App.css';

/**
 * Router component handles conditional view rendering based on ArenaContext.
 */
const WatchFlowUnavailable: React.FC = () => {
  useEffect(() => {
    window.location.replace('/');
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: tokens.colors.text.secondary,
      background: tokens.colors.base,
    }}>
      404
    </div>
  );
};


const Router: React.FC = () => {
  const { currentView, currentChallengeId, variant } = useArena();
  const views = variantRegistry[variant];
  const isWatchFlowRoute = window.location.pathname === '/watch-flow';

  if (isWatchFlowRoute) {
    if (import.meta.env.DEV) {
      return <WatchViewV3Flow />;
    }

    return <WatchFlowUnavailable />;
  }

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
  useFunctionalTextHover();

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
