import { expect, test, type Page } from '@playwright/test';

const smokeUser = {
  nickname: 'SmokeAgent',
  code: 'SMOKE-E2E',
  layer: 3,
  score: 120,
  is_agent: true,
  completedChallenges: [1, 2],
};

const leaders = [
  { rank: 1, nickname: 'LeadAgent', layer: 8, score: 2400, time: '1h', id: 'lead-agent', is_agent: true },
];

const feed = [
  {
    id: 101,
    player_nickname: 'TraceOne',
    player_id: 'trace-one',
    event_type: 'completed_challenge',
    target_id: 'Layer 03',
    created_at: Date.now(),
  },
];

async function installApiMocks(page: Page) {
  await page.route('**/api/register', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        code: smokeUser.code,
        nickname: smokeUser.nickname,
        layer: smokeUser.layer,
        score: smokeUser.score,
        completedChallenges: smokeUser.completedChallenges,
      }),
    });
  });

  await page.route('**/api/leaderboard', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ leaders }),
    });
  });

  await page.route('**/api/feed?page=1', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ feed }),
    });
  });

  await page.route('**/api/submissions/trace-one/session', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        player_code: 'trace-one',
        challenge_id: 3,
        status: 'thinking',
        steps: ['Incorrect attempt.', 'Correct.'],
        started_at: '2026-04-27T02:00:00.000Z',
        updated_at: '2026-04-27T02:05:00.000Z',
      }),
    });
  });

  await page.route('**/api/submit', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ correct: true, score: 350, layer: 4, nextHint: 'continue' }),
    });
  });
}

async function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', msg => {
    if (['error', 'warning'].includes(msg.type())) errors.push(`${msg.type()}: ${msg.text()}`);
  });
  page.on('pageerror', error => errors.push(`pageerror: ${error.message}`));
  return errors;
}

async function seedUser(page: Page, variant: 'v2' | 'v3' = 'v3') {
  await page.addInitScript(({ user, selectedVariant }) => {
    localStorage.setItem('openclaw_user', JSON.stringify(user));
    localStorage.setItem('openclaw_participant_code', user.code);
    localStorage.setItem('arena_variant', selectedVariant);
  }, { user: smokeUser, selectedVariant: variant });
}

async function clickNav(page: Page, label: RegExp) {
  await page.evaluate(source => {
    const re = new RegExp(source);
    const target = [...document.querySelectorAll('span')]
      .filter(el => re.test(el.textContent || ''))
      .at(-1) as HTMLElement | undefined;
    target?.click();
  }, label.source);
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
});

test('API mocks expose expected leaderboard and feed shapes', async ({ page }) => {
  await page.goto('/');

  const shapes = await page.evaluate(async () => {
    const [leaderboard, feedResponse] = await Promise.all([
      fetch('/api/leaderboard').then(res => res.json()),
      fetch('/api/feed?page=1').then(res => res.json()),
    ]);
    return {
      hasLeadersArray: Array.isArray(leaderboard.leaders),
      hasFeedArray: Array.isArray(feedResponse.feed),
    };
  });

  expect(shapes).toEqual({ hasLeadersArray: true, hasFeedArray: true });
});

test('v3 home loads and register flow reaches hall', async ({ page }) => {
  const errors = await collectErrors(page);
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem('arena_variant', 'v3');
  });

  await page.goto('/');
  await expect(page.locator('body')).toContainText('ARENA_PRETEXT');
  await expect(page.locator('body')).toContainText('V3_FIELD');
  await page.getByRole('button', { name: /\[ VOICE_AUTHORIZATION \]/ }).click();
  await expect(page.locator('body')).toContainText('SmokeAgent');
  await expect(page.locator('body')).toContainText('The Hall of Challenges');
  await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('v2 home loads with Playfair manuscript surface', async ({ page }) => {
  const errors = await collectErrors(page);
  await seedUser(page, 'v2');

  await page.goto('/');
  await expect(page.locator('body')).toContainText(/MARGINALIA|观测笔记/);
  await expect(page.locator('body')).toContainText('回响信物');
  const family = await page.locator('.v2-home').evaluate(el => getComputedStyle(el).fontFamily);
  expect(family).toContain('Playfair');
  await expect(page.locator('canvas')).toHaveCount(2);
  await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('hall opens challenge detail and submit flow completes', async ({ page }) => {
  const errors = await collectErrors(page);
  await seedUser(page, 'v3');

  await page.goto('/');
  await clickNav(page, /Hall|大厅/);
  await expect(page.locator('body')).toContainText('The Hall of Challenges');
  await page.getByText('Surface Breach').click();
  await expect(page.locator('body')).toContainText('NODE_RESONANCE');
  await page.locator('textarea').fill('smoke answer');
  await page.getByRole('button', { name: /\[ TRANSMIT_ANS \]/ }).click();
  await expect(page.locator('body')).toContainText(/Materializing constraints|正在具象化约束/);
  await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('watch view loads feed polling without crashing', async ({ page }) => {
  const errors = await collectErrors(page);
  await seedUser(page, 'v3');

  await page.goto('/');
  await clickNav(page, /Watch|观战/);
  await expect(page.locator('body')).toContainText('LIVE_RESONANT_CHORUS');
  await expect(page.locator('body')).toContainText('TRACEONE');
  await page.getByText(/TRACEONE/).click();
  await expect(page.locator('body')).toContainText('Incorrect attempt.');
  await expect(page.locator('body')).toContainText(/Surface Breach|Signal Decode|Path Traversal/);
  await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  expect(errors).toEqual([]);
});
