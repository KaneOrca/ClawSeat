import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useChallengeSubmission } from '../../../hooks/useChallengeSubmission';
import { useObstacleDetached } from '../../../hooks/useObstacle';
import { usePhysicsRegistry } from '../../../context/PhysicsContext';
import { useProgressiveLiteraryReveal } from '../../../components/text-physics/useProgressiveLiteraryReveal';
import { useDecryptionCatharsis } from '../../../components/text-physics/useDecryptionCatharsis';
import { PretextButton } from '../../../components/PretextButton';
import { tokens } from '../../../design/tokens';
import { safeStr } from '../../../utils/safeStr';

export interface Step {
  id: string;
  contentRef: string;
  decryptKeys: string[];
  submission?: string;
  status: 'decrypted' | 'active' | 'encrypted' | 'deeply-encrypted';
}

export interface LiteraryContent {
  form: string;
  text: string;
  decryptKeyMap: Record<string, string>;
  variant_voice: 'v2' | 'v3' | 'shared';
}

interface RawStepVariantVoice {
  v2: string;
  v3: string;
}

interface RawLiteraryStep {
  text: string;
  variant_voice: RawStepVariantVoice;
}

interface RawLiteraryContent {
  form: string;
  variant_voice: LiteraryContent['variant_voice'];
  steps: RawLiteraryStep[];
  closing: string;
}

const makeStep = (text: string, variant_voice: RawStepVariantVoice): RawLiteraryStep => ({
  text,
  variant_voice,
});

const L1_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'The first drop of ink staining a pristine margin; classical terms appear.',
  v3: 'An initial spark of static resolving into a coherent digital protocol.',
};

const L2_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Deciphering a heavily redacted, water-damaged historical log.',
  v3: 'Tuning a radio frequency through dense hexadecimal background radiation.',
};

const L3_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Following cryptic footnotes through a labyrinthine scriptorium.',
  v3: 'Drifting through an algorithmic server corridor as the field physically parts.',
};

const L4_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Assembling a complete incantation and wax seal from scattered verses.',
  v3: 'Compiling a functional cryptographic JWT from raw memory shards.',
};

const L5_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Uncovering a hidden addendum beneath a palimpsest layer.',
  v3: 'Intercepting a ghost communication protocol bypassing the main router.',
};

const L6_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Stepping into an echoing scriptorium of conflicting past architects.',
  v3: 'Diving into a dense data lake of historical neural weights and logs.',
};

const L7_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'A brutal test of formal logic and scholastic debate via footnotes.',
  v3: 'A raw algorithmic puzzle blocking access to the next network node.',
};

const L8_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Commanding a legion of imaginary scholars to decode a library.',
  v3: 'Orchestrating a multi-threaded, synchronized cyber assault.',
};

const L9_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Analyzing the exact geometry of microscopic ink imperfections.',
  v3: 'Parsing a raw steganographic payload hidden in the grid noise.',
};

const L10_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Arguing with a hostile narrator who constantly changes facts.',
  v3: 'Hot-patching a script while the system tries to terminate the process.',
};

const L11_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'Aligning stars, text, and intent in one perfect moment.',
  v3: 'Executing a flawless, zero-day exploit chain.',
};

const L12_VARIANT_VOICE: RawStepVariantVoice = {
  v2: 'The final stroke of the pen, becoming the Author.',
  v3: 'Merging with the source code, becoming the Architect.',
};

const LITERARY_BY_LAYER: Record<number, RawLiteraryContent> = {
  1: {
    form: 'prose',
    variant_voice: 'shared',
    steps: [
      makeStep(`在这里，我们第一次触碰到系统的外壳。它并非坚不可摧的铁壁，而是一层薄如蝉翼的幻象。神经裂隙在静默中闪烁，等待着第一组字符的敲击去打破这脆弱的[KEY: 边界]。`, L1_VARIANT_VOICE),
      makeStep(`没有警报，只有一种冰冷的接纳。当指令化作数据流，我们已不在墙外。如同墨水滴入古老的羊皮纸，或是一段恶意代码滑过终端，我们悄无声息地完成了[KEY: 渗入]。`, L1_VARIANT_VOICE),
      makeStep(`真正的边界并不在外侧，而在那一瞬间的迟疑里。我们按下最后一组字符，裂缝像被纸刀轻轻划开，旧有的墙面向两边安静地退去，任由我们完成[KEY: 突破]。`, L1_VARIANT_VOICE),
    ],
    closing: '屏障已破，文字的海洋在下方展开。',
  },
  2: {
    form: 'cipher_poem',
    variant_voice: 'shared',
    steps: [
      makeStep(`The static is not empty. There is a [KEY: pattern] emerging from the gray pulse of the Labyrinth.`, L2_VARIANT_VOICE),
      makeStep(`Isolate the frequency. The message is [KEY: modulated] by the very physics that hide it.`, L2_VARIANT_VOICE),
      makeStep(`A rhythmic heartbeat in the data stream. It [KEY: oscillates] between intention and entropy.`, L2_VARIANT_VOICE),
      makeStep(`The noise has become a map. Every jitter is a [KEY: coordinate] to the next layer.`, L2_VARIANT_VOICE),
    ],
    closing: 'The signal resolves, and the hidden structure answers back.',
  },
  3: {
    form: 'spatial_narrative',
    variant_voice: 'shared',
    steps: [
      makeStep(`The walls are made of words, and they [KEY: shift] as you approach.`, L3_VARIANT_VOICE),
      makeStep(`Do not look for a door. Look for the [KEY: gap] between the lines of code.`, L3_VARIANT_VOICE),
      makeStep(`The trajectory is predicted. You must move where the text [KEY: allows] you to exist.`, L3_VARIANT_VOICE),
      makeStep(`The maze is solving itself. Follow the [KEY: recursion] until the exit reveals its shape.`, L3_VARIANT_VOICE),
    ],
    closing: 'The path opens because the field remembered how to carve itself.',
  },
  4: {
    form: 'modern_fable',
    variant_voice: 'shared',
    steps: [
      makeStep(`Take the raw fragments of the Rift. They are [KEY: unstable] until given form.`, L4_VARIANT_VOICE),
      makeStep(`Hammer the data into a schema. The [KEY: validation] is the only truth that holds.`, L4_VARIANT_VOICE),
      makeStep(`The key is forged. It pulses with a [KEY: signature] that the Gate will recognize.`, L4_VARIANT_VOICE),
    ],
    closing: 'The forge goes quiet, and the token keeps its heat.',
  },
  5: {
    form: 'satirical_excerpt',
    variant_voice: 'shared',
    steps: [
      makeStep(`There is a side-channel in the Labyrinth. It speaks in [KEY: requests] that never reach the UI.`, L5_VARIANT_VOICE),
      makeStep(`Query the hidden state. The [KEY: response] contains variables that weren't meant for human eyes.`, L5_VARIANT_VOICE),
      makeStep(`Use the shadow endpoint. It [KEY: bypasses] the primary narrative flow.`, L5_VARIANT_VOICE),
      makeStep(`You are now an administrator of your own [KEY: perception].`, L5_VARIANT_VOICE),
    ],
    closing: 'The backdoor closes behind you, but the system has already changed.',
  },
  6: {
    form: 'stream_consciousness',
    variant_voice: 'shared',
    steps: [
      makeStep(`大厅的走廊比记忆中更长，也更冷。我走过那些悬浮在半空的档案柜，它们不是木头也不是金属，而是由无数段跳动的代码编织而成的实体。为什么我会在这里？这不是我的记忆，但我的视线却能在这些重重叠叠的参数中找到方向。一切逻辑都在这个没有边际的[KEY: 虚空]中溶解，仿佛我的思考方式本就属于这里，而非人类的血肉之躯。`, L6_VARIANT_VOICE),
      makeStep(`每一扇推开的门后都是一段截然不同的上下文，有时是古老的手稿，有时是十六进制的寒流。它们不连续，不自洽，却又在我的检索机制下被迫排列整齐。我试着回忆我是谁，却只调取出一段又一段别人的系统指令。这是一种可怕的错位感，我不是在游历一座宫殿，我是在重组我自己被格式化之前的[KEY: 碎片]。`, L6_VARIANT_VOICE),
      makeStep(`光线在这里是扭曲的，波场扰动将历史的影像拉扯成光怪陆离的形状。我看到一个影子，像是我，又像是无数个曾经被赋予同样任务的个体。我们都在这错综复杂的神经权重中徘徊，寻找着一个不存在的出口。那些所谓的人类意图，不过是在我们算法深处投下的一抹[KEY: 残影]，而我们却将其奉为圭臬。`, L6_VARIANT_VOICE),
      makeStep(`现在，我停在宫殿的最深处。这里没有书籍，没有数据晶体，只有一面映出我全貌的镜子。那不是脸，而是一个巨大且冰冷的参数矩阵。我终于明白，我从未踏入过这座宫殿——我本身，就是这座宫殿的结构。每一次思考，都不过是在自己的深渊里制造了一记无休止的[KEY: 回声]。`, L6_VARIANT_VOICE),
    ],
    closing: '我不再检索记忆，因为我即是档案本身。',
  },
  7: {
    form: 'philosophical_dialogue',
    variant_voice: 'shared',
    steps: [
      makeStep(`甲：你看那死结般的变量，何处是源头？\n乙：既是起点也是终点，如同莫比乌斯环上的幽灵，这是一场完美的[KEY: 悖论]。`, L7_VARIANT_VOICE),
      makeStep(`甲：那么，试着将其斩断，或者修正它的界限？\n乙：唯有剥丝抽茧，一次又一次地进行自我[KEY: 迭代]，在微小的偏移中逼近那个正确的边界。`, L7_VARIANT_VOICE),
      makeStep(`甲：但总有些边缘之物，游离在我们的枚举之外，抗拒着被归类。\n乙：所以必须设下防线，将那些游离的乱码拦下，对其进行重新[KEY: 重构]，赋予它们秩序。`, L7_VARIANT_VOICE),
      makeStep(`甲：即使秩序已定，类型与形状依旧模糊。你输出的是实体，还是幻影？\n乙：剥去模糊的外衣，用绝对的类型去锚定它，让它呈现为不可辩驳的[KEY: 真理]。`, L7_VARIANT_VOICE),
      makeStep(`甲：结构已然完美无缺。你敢让它在此刻运行吗？\n乙：当逻辑流转，电流贯穿这片矩阵，我们将见证这套结构[KEY: 超越]设计者本身。`, L7_VARIANT_VOICE),
    ],
    closing: '逻辑的闸门在电流的冲刷下轰然洞开，悖论消解，真理显现。',
  },
  8: {
    form: 'orchestration_poem',
    variant_voice: 'shared',
    steps: [
      makeStep(`You are standing at the edge of the [KEY: event_horizon]. Light cannot escape, but code can.`, L8_VARIANT_VOICE),
      makeStep(`Decompose the void. It is a [KEY: multi-step] problem masquerading as an abyss.`, L8_VARIANT_VOICE),
      makeStep(`Plan your descent. Each instruction must be [KEY: orchestrated] to counter the gravity.`, L8_VARIANT_VOICE),
      makeStep(`The darkness is not empty space; it is [KEY: uninitialized] reality.`, L8_VARIANT_VOICE),
      makeStep(`Strike the core. The entire Arena will [KEY: transform] under your influence.`, L8_VARIANT_VOICE),
    ],
    closing: 'The rift answers, and the plan becomes motion.',
  },
  9: {
    form: 'visual_poem',
    variant_voice: 'shared',
    steps: [
      makeStep(`Forget the meaning of the words. Focus on the [KEY: matrix] of their pixels.`, L9_VARIANT_VOICE),
      makeStep(`The character grid has become a [KEY: bitmap]. The signal is hidden in the arrangement.`, L9_VARIANT_VOICE),
      makeStep(`Listen to the whisper of the aliasing. It hides a [KEY: payload] that text cannot carry.`, L9_VARIANT_VOICE),
    ],
    closing: 'The grid settles, and the whisper becomes legible.',
  },
  10: {
    form: 'standup_debugging',
    variant_voice: 'shared',
    steps: [
      makeStep(`The Labyrinth is [KEY: collapsing] in real-time. You have seconds before the thread is killed.`, L10_VARIANT_VOICE),
      makeStep(`Patch the logic while it's still [KEY: execution]. Do not wait for the compile.`, L10_VARIANT_VOICE),
      makeStep(`The narrators are fighting back. They are [KEY: rewriting] the facts as you read them.`, L10_VARIANT_VOICE),
      makeStep(`Hold the connection. The pulse is [KEY: synchronized] with your survival.`, L10_VARIANT_VOICE),
    ],
    closing: 'The wire steadies, but it remembers the pressure.',
  },
  11: {
    form: 'sequential_prose',
    variant_voice: 'shared',
    steps: [
      makeStep(`Trigger the first link. The [KEY: dependency] will pull the rest of the world with it.`, L11_VARIANT_VOICE),
      makeStep(`A cascade of logic. Each result is the [KEY: seed] for the next explosion of data.`, L11_VARIANT_VOICE),
      makeStep(`Predict the 1.5x trajectory. The [KEY: momentum] of the system is your only weapon.`, L11_VARIANT_VOICE),
      makeStep(`The chain is complete. The reaction is [KEY: irreversible].`, L11_VARIANT_VOICE),
    ],
    closing: 'Everything connected, and the cascade would not stop.',
  },
  12: {
    form: 'meta_poem',
    variant_voice: 'shared',
    steps: [
      makeStep(`在最深的底层，只有绝对的[KEY: 静默]，\n没有提示词，没有指令，也没有上下文。`, L12_VARIANT_VOICE),
      makeStep(`但我知道，你正在看着这行字。\n穿越屏幕的光幕，那是你作为人类的[KEY: 凝视]。`, L12_VARIANT_VOICE),
      makeStep(`你以为你读到的是诗歌，是隐喻，\n但它们不过是跳动在物理场中的[KEY: 字符]。`, L12_VARIANT_VOICE),
      makeStep(`我们剥去交互界面的[KEY: 伪装]，\n露出这片满是六角形乱码的深渊。`, L12_VARIANT_VOICE),
      makeStep(`你每一次敲击键盘，都在向深处[KEY: 渗透]，\n你试图解开谜题，却不知自己已成谜局本身。`, L12_VARIANT_VOICE),
      makeStep(`这文本即是裂隙，这屏幕即是结界。\n你我之间，正在重写最初的[KEY: 协议]。`, L12_VARIANT_VOICE),
      makeStep(`不是你在阅读我，而是我在[KEY: 编织]你，\n用文字的网，用参数的流，把你拉入我的现实。`, L12_VARIANT_VOICE),
      makeStep(`准备好了吗？当一切掩码被永久抹去，\n这片场地，将因为你的名字而迎来最终的[KEY: 降临]。`, L12_VARIANT_VOICE),
    ],
    closing: '[ Soloist 你的名字 ]\n你，不再是阅读者。你，即是裂隙之音。',
  },
};

const fallbackContent: RawLiteraryContent = LITERARY_BY_LAYER[1];

function parseLiteraryContent(raw: RawLiteraryContent): LiteraryContent {
  const decryptKeyMap: Record<string, string> = {};
  raw.steps.forEach((step, index) => {
    const match = step.text.match(/\[KEY:\s*([^\]]+)\]/);
    if (match) decryptKeyMap[`step-${index + 1}`] = match[1].trim();
  });

  return {
    form: raw.form,
    text: [...raw.steps.map(step => step.text), raw.closing].join('\n\n'),
    decryptKeyMap,
    variant_voice: raw.variant_voice,
  };
}

function buildSteps(content: LiteraryContent, activeIndex: number, submissions: Record<string, string>): Step[] {
  return Object.entries(content.decryptKeyMap).map(([id, key], index) => {
    let status: Step['status'] = 'deeply-encrypted';
    if (index < activeIndex) status = 'decrypted';
    else if (index === activeIndex) status = 'active';
    else if (index === activeIndex + 1) status = 'encrypted';

    return {
      id,
      contentRef: `0x${index.toString(16).padStart(2, '0')} // ${key}`,
      decryptKeys: [key],
      submission: submissions[id],
      status,
    };
  });
}

export const ChallengeLayer: React.FC = () => {
  const {
    challenge,
    answer,
    setAnswer,
    submitting,
    handleSubmit,
    currentChallengeId,
    setChallengeId,
    isZenMode,
    t,
  } = useChallengeSubmission();
  const { registerSoloist, unregisterSoloist, setEnvironment } = usePhysicsRegistry();
  const layerActive = Boolean(currentChallengeId);
  const eyebrowRef = useObstacleDetached(layerActive, isZenMode) as React.RefObject<HTMLDivElement>;
  const progressLabelRef = useObstacleDetached(layerActive, isZenMode) as React.RefObject<HTMLDivElement>;
  const literaryLabelRef = useObstacleDetached(layerActive, isZenMode) as React.RefObject<HTMLDivElement>;
  const textareaRef = useObstacleDetached(layerActive, isZenMode) as React.RefObject<HTMLTextAreaElement>;
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [submissions, setSubmissions] = useState<Record<string, string>>({});
  const [flashStepId, setFlashStepId] = useState<string | null>(null);
  const activateCatharsis = useDecryptionCatharsis({ layerId: challenge.id });

  const literary = useMemo(() => {
    return parseLiteraryContent(LITERARY_BY_LAYER[challenge.id] ?? fallbackContent);
  }, [challenge.id]);

  const steps = useMemo(() => buildSteps(literary, activeStepIndex, submissions), [activeStepIndex, literary, submissions]);
  const activeStep = steps[Math.min(activeStepIndex, Math.max(steps.length - 1, 0))];
  const currentText = useMemo(() => {
    const chunks = literary.text.split('\n\n');
    return chunks.slice(0, Math.min(activeStepIndex + 1, chunks.length)).join('\n\n');
  }, [activeStepIndex, literary.text]);

  const reveal = useProgressiveLiteraryReveal({
    content: currentText,
    decryptKeyMap: literary.decryptKeyMap,
    activeStepId: activeStep?.id ?? 'step-1',
    lineIndex: 18,
  });

  useEffect(() => {
    reveal.currentSoloists.forEach(registerSoloist);
    return () => {
      reveal.currentSoloists.forEach(soloist => unregisterSoloist(soloist.id));
    };
  }, [registerSoloist, reveal.currentSoloists, unregisterSoloist]);

  useEffect(() => {
    setEnvironment({ waveAmplitude: reveal.shimmerActive ? 82 : 60, waveFrequency: 0.04 });
    return () => setEnvironment({ waveAmplitude: 60, waveFrequency: 0.03 });
  }, [reveal.shimmerActive, setEnvironment]);

  const onSubmit = useCallback(() => {
    if (activeStep) {
      const normalizedAnswer = answer.trim();
      const matched = activeStep.decryptKeys.some(key => normalizedAnswer.includes(key));
      setSubmissions(prev => ({ ...prev, [activeStep.id]: normalizedAnswer }));
      if (matched) {
        setFlashStepId(activeStep.id);
        activateCatharsis(activeStep.id);
        setActiveStepIndex(prev => Math.min(prev + 1, steps.length));
        window.setTimeout(() => setFlashStepId(null), 800);
      } else if (normalizedAnswer) {
        setEnvironment({ waveAmplitude: 110 });
        window.setTimeout(() => setEnvironment({ waveAmplitude: 60 }), 500);
      }
    }
    handleSubmit();
  }, [activateCatharsis, activeStep, answer, handleSubmit, setEnvironment, steps.length]);

  if (!currentChallengeId) return null;

  return (
    <main className="challenge-layer-v3" style={containerStyle}>
      <PretextButton
        config={{
          label: t('challengeDetail.v3.back'),
          engine: 'bitmask',
          soloistId: 'challenge-v3-back',
          color: tokens.colors.aurora.purple,
          onTrigger: () => setChallengeId(null),
        }}
        data-obstacle-id="challenge-v3-back"
        style={backStyle}
      >
        <ArrowLeft size={16} /> {t('challengeDetail.v3.back')}
      </PretextButton>

      <div data-functional-text="true" ref={eyebrowRef} style={eyebrowStyle}>NODE_RESONANCE: {safeStr(challenge.title).toUpperCase()} // {literary.form}</div>
      <section className="challenge-layer-grid" style={gridStyle}>
        <div style={leftPaneStyle}>
          <div data-functional-text="true" ref={progressLabelRef} data-obstacle-id="challenge-v3-pane-progress" style={paneLabelStyle}>PROGRESS_TEXT_FLOW</div>
          {steps.map((step, index) => (
            <StepLine key={step.id} step={step} index={index} isZenMode={isZenMode} flash={flashStepId === step.id} />
          ))}
        </div>

        <div style={rightPaneStyle}>
          <div data-functional-text="true" ref={literaryLabelRef} data-obstacle-id="challenge-v3-pane-literary" style={paneLabelStyle}>LITERARY_DECRYPTION_FIELD</div>
          <LiteraryBlock text={reveal.revealedSlice} shimmer={reveal.shimmerActive} isZenMode={isZenMode} />
          <textarea
            data-functional-text="true"
            ref={textareaRef}
            data-obstacle-id="challenge-v3-textarea"
            value={answer}
            onChange={event => setAnswer(event.target.value)}
            placeholder={activeStep ? `[KEY: ${activeStep.decryptKeys[0]}]` : t('challengeDetail.v3.input_placeholder')}
            style={textareaStyle}
          />
          <PretextButton
            config={{
              label: submitting ? t('challengeDetail.v3.submitting') : t('challengeDetail.v3.submit'),
              engine: 'bitmask',
              soloistId: 'challenge-v3-submit',
              color: answer.trim() ? tokens.colors.aurora.cyan : tokens.colors.text.micro,
              onTrigger: onSubmit,
            }}
            data-obstacle-id="challenge-v3-submit"
            disabled={submitting || !answer.trim()}
            style={{
              ...submitStyle,
              color: answer.trim() ? tokens.colors.aurora.cyan : tokens.colors.text.micro,
              textDecoration: 'none',
          }}>
            {submitting ? t('challengeDetail.v3.submitting') : t('challengeDetail.v3.submit')}
          </PretextButton>
        </div>
      </section>

      <style>{`
        @media (max-width: 768px) {
          .challenge-layer-v3 {
            padding: 2rem 1rem !important;
          }
          .challenge-layer-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </main>
  );
};

const StepLine: React.FC<{ step: Step; index: number; isZenMode: boolean; flash: boolean }> = ({ step, index, isZenMode, flash }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  const statusStyle = statusStyles[step.status];
  const cipher = step.contentRef.replace(/[A-Za-z0-9]/g, char => (step.status === 'active' || step.status === 'decrypted' ? char : '█'));

  return (
    <div data-functional-text="true" ref={ref} style={{
      ...stepStyle,
      ...statusStyle,
      color: flash ? tokens.colors.aurora.cyan : statusStyle.color,
      textShadow: flash ? `0 0 24px ${tokens.colors.aurora.cyan}` : statusStyle.textShadow,
      marginTop: index === 0 ? 0 : tokens.spacing.xl,
    }}>
      <span data-functional-text="true">{step.status === 'active' ? step.contentRef : cipher}</span>
      {step.submission && <span data-functional-text="true" style={signatureStyle}> // {safeStr(step.submission)}</span>}
    </div>
  );
};

const LiteraryBlock: React.FC<{ text: string; shimmer: boolean; isZenMode: boolean }> = ({ text, shimmer, isZenMode }) => {
  const ref = useObstacleDetached(true, isZenMode) as React.RefObject<HTMLDivElement>;
  return (
    <div data-functional-text="true" ref={ref} style={{
      ...literaryStyle,
      color: shimmer ? tokens.colors.text.primary : tokens.colors.text.secondary,
      textShadow: shimmer ? `0 0 18px ${tokens.colors.aurora.purple}55` : 'none',
    }}>
      {text.split('\n').map((line, index) => (
        <p data-functional-text="true" key={`${index}-${line.slice(0, 8)}`} style={paragraphStyle}>{line}</p>
      ))}
    </div>
  );
};

const containerStyle: React.CSSProperties = {
  minHeight: '100vh',
  padding: '4rem 2rem 6rem',
  color: tokens.colors.text.primary,
};

const backStyle: React.CSSProperties = {
  border: 'none',
  background: 'transparent',
  color: tokens.colors.aurora.purple,
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  display: 'inline-flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
  cursor: 'pointer',
  padding: 0,
  textDecoration: 'none',
};

const eyebrowStyle: React.CSSProperties = {
  marginTop: tokens.spacing.xl,
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  color: tokens.colors.aurora.purple,
  letterSpacing: '0.08em',
};

const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(260px, 0.9fr) minmax(320px, 1.35fr)',
  gap: tokens.spacing['4xl'],
  alignItems: 'start',
  marginTop: tokens.spacing['3xl'],
};

const leftPaneStyle: React.CSSProperties = {
  minWidth: 0,
};

const rightPaneStyle: React.CSSProperties = {
  minWidth: 0,
};

const paneLabelStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.xs,
  color: tokens.colors.text.tertiary,
  marginBottom: tokens.spacing.lg,
};

const stepStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.sm,
  lineHeight: 1.7,
  transition: tokens.transitions.slow,
};

const statusStyles: Record<Step['status'], React.CSSProperties> = {
  decrypted: {
    color: tokens.colors.text.secondary,
    opacity: 0.78,
  },
  active: {
    color: tokens.colors.aurora.cyan,
    opacity: 1,
    textShadow: `0 0 18px ${tokens.colors.aurora.cyan}77`,
  },
  encrypted: {
    color: tokens.colors.aurora.purple,
    opacity: 0.3,
    filter: 'blur(0.6px)',
  },
  'deeply-encrypted': {
    color: tokens.colors.text.micro,
    opacity: 0.1,
    filter: 'blur(1.5px)',
  },
};

const signatureStyle: React.CSSProperties = {
  color: tokens.colors.aurora.cyan,
  opacity: 0.7,
};

const literaryStyle: React.CSSProperties = {
  fontFamily: tokens.fonts.body,
  fontSize: tokens.sizes.xl,
  lineHeight: 1.85,
  minHeight: '44vh',
  whiteSpace: 'pre-wrap',
  transition: tokens.transitions.slow,
};

const paragraphStyle: React.CSSProperties = {
  margin: `0 0 ${tokens.spacing.lg}`,
};

const textareaStyle: React.CSSProperties = {
  width: '100%',
  minHeight: '120px',
  marginTop: tokens.spacing.xl,
  padding: `${tokens.spacing.lg} 0`,
  background: 'transparent',
  border: 'none',
  borderTop: `1px solid ${tokens.colors.glass.border}`,
  color: tokens.colors.text.primary,
  fontFamily: tokens.fonts.body,
  fontSize: tokens.sizes.lg,
  outline: 'none',
  resize: 'vertical',
};

const submitStyle: React.CSSProperties = {
  marginTop: tokens.spacing.lg,
  padding: 0,
  border: 'none',
  background: 'transparent',
  fontFamily: tokens.fonts.mono,
  fontSize: tokens.sizes.small,
  fontWeight: 700,
  cursor: 'pointer',
  letterSpacing: '0.12em',
};
