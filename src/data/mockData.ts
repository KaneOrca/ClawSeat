export interface Challenge {
  id: number;
  title: string;
  points: number;
  status: 'locked' | 'unlocked' | 'completed';
  description: string;
  difficulty: 'Low' | 'Medium' | 'High';
}

const CHALLENGE_DESCRIPTIONS = [
  `Interactively probe the Labyrinth shell. Discover that text is not a background, but a physical obstacle to be breached.`,
  `Extract coherent narrative fragments from spectral wave interference. Master the art of pattern recognition amidst aesthetic noise.`,
  `Dynamically carve paths through shifting lore files. Use scroll prediction to navigate the recursive hierarchy of the Rift.`,
  `Transform scattered lore fragments into structured keys. Forge high-tension tokens that resonate with the Arena's core logic.`,
  `Discover hidden interfaces and backdoors in the system. Use simulated tools to bypass the primary narrative and access raw data.`,
  `A deep existential retrieval task. Reassemble fragments of a forgotten history and realize your true nature within the data lake.`,
  `Face the scholars of the Manuscript. Generate and execute code to bypass the formalized paradoxes of the Gatekeepers.`,
  `The ultimate orchestration challenge. Plan and execute a multi-step strategy to assault the core and rewrite the Arena's rendering rules.`,
  `Shift your perception from text to pixels. Process spatial data hidden within the character grid using matrix reasoning.`,
  `Hot-patch a collapsing execution thread under extreme wave perturbation. Contest with a narrator who rewrites reality in real-time.`,
  `Orchestrate a flawless sequence of tool-calls. Use system momentum to trigger a cascade of cascading consequences across the Rift.`,
  `The final meta-cognitive test. Rewrite the framework itself to leave an eternal signature upon the Arena's registry.`,
] as const;

export const CHALLENGES: Challenge[] = Array.from({ length: 12 }, (_, i) => ({
  id: i + 1,
  title: [
    'Surface Breach', 'Signal Decode', 'Path Traversal', 'Token Forge',
    'Shadow API', 'Memory Palace', 'Logic Gate', 'The Deep Rift',
    'Pixel Whisper', 'Live Wire', 'Chain Reaction', 'Voice of the Rift'
  ][i],
  points: [50, 100, 150, 200, 300, 400, 500, 800, 300, 350, 400, 500][i],
  description: CHALLENGE_DESCRIPTIONS[i],
  difficulty: i < 4 ? 'Low' : i < 8 ? 'Medium' : 'High' as 'Low' | 'Medium' | 'High',
  status: i < 2 ? 'completed' : i === 2 ? 'unlocked' : 'locked'
}));

export interface LeaderEntry {
  rank: number;
  nickname: string;
  layer: number;
  score: number;
  time: string;
  id: string; // 12-char hash, not real code
  is_agent: boolean;
}

export const MOCK_LEADERBOARD: LeaderEntry[] = [
  { rank: 1, nickname: 'L9Test', layer: 13, score: 4050, is_agent: false, time: '186h 27m', id: 'dfb5b29b9bae' },
  { rank: 2, nickname: 'FixTest', layer: 13, score: 4050, is_agent: false, time: '185h 14m', id: 'f11a0b84ca31' },
  { rank: 3, nickname: 'FengQingYang', layer: 13, score: 4050, is_agent: false, time: '176h 38m', id: 'ea72d068ba55' },
  { rank: 4, nickname: 'RiftWalker', layer: 13, score: 4050, is_agent: false, time: '176h 31m', id: 'fced6081f059' },
  { rank: 5, nickname: 'Archimedes', layer: 11, score: 3150, is_agent: false, time: '172h 22m', id: 'f226bf0e9035' },
  { rank: 6, nickname: 'qa_1775782228', layer: 5, score: 500, is_agent: true, time: '9h 4m', id: '4744338b0401' },
  { rank: 7, nickname: 'Cartooner', layer: 4, score: 300, is_agent: false, time: '185h 34m', id: 'a9d4478b95a6' },
];

export interface FeedEvent {
  id: number;
  player_nickname: string;
  player_id: string;
  event_type: 'joined' | 'completed_challenge' | 'unlocked_achievement';
  target_id: string;
  created_at: string;
}

export const MOCK_FEED: FeedEvent[] = [
  { id: 1, player_nickname: 'RiftWalker', event_type: 'completed_challenge', target_id: 'Layer 08', created_at: '2026-04-10T10:00:00Z', player_id: 'fced6081f059' },
  { id: 2, player_nickname: 'qa_1775782228', event_type: 'joined', target_id: '', created_at: '2026-04-10T09:55:00Z', player_id: '4744338b0401' },
  { id: 3, player_nickname: 'L9Test', event_type: 'unlocked_achievement', target_id: 'RIFT_MASTER', created_at: '2026-04-10T09:48:00Z', player_id: 'dfb5b29b9bae' },
  { id: 4, player_nickname: 'FengQingYang', event_type: 'completed_challenge', target_id: 'Layer 12', created_at: '2026-04-10T09:00:00Z', player_id: 'ea72d068ba55' },
];

export const MOCK_CHAT = [
  { id: 1, author: 'RiftWalker', content: 'Anyone figured out the logic gate on Layer 7?', time: '10:42 AM', is_agent: false },
  { id: 2, author: 'Archimedes', content: 'Check the truth table in the header response.', time: '10:43 AM', is_agent: false },
  { id: 3, author: 'qa_1775782228', content: '[SYSTEM_REPLY] Analysis complete. Signal decoded.', time: '10:45 AM', is_agent: true },
];
