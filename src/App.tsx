import React from 'react';
import { ArenaProvider, useArena } from './context/ArenaContext';
import { LanguageProvider } from './context/LanguageContext';
import { PhysicsProvider } from './context/PhysicsContext';
import { MainLayout } from './layouts/MainLayout';
import { variantRegistry } from './variants/registry';

// Shared Views (not variant-specific)
import { CommunityView } from './views/Community/CommunityView';

import './index.css';

const CodeMorphRoute = React.lazy(() =>
  import('./spike/CodeMorphRoute').then(module => ({ default: module.CodeMorphRoute }))
);

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
    case 'challenges': {
      const Hall = views.hall;
      return <Hall />;
    }
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

const AppContent: React.FC = () => {
  const { currentView } = useArena();
  const isCodeMorphSpike = import.meta.env.DEV && (
    currentView === 'spike-code-morph' ||
    window.location.pathname === '/spike/code-morph' ||
    new URLSearchParams(window.location.search).get('spike') === 'code-morph'
  );

  if (isCodeMorphSpike) {
    return (
      <React.Suspense fallback={null}>
        <CodeMorphRoute />
      </React.Suspense>
    );
  }

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
