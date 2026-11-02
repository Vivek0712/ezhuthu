import { act, fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { enHow, taHow } from '../../i18n/strings-how';
import { HowItWorksPage } from '../../pages/HowItWorksPage';
import { renderApp } from '../../test/render';
import { AgentChips } from './AgentChips';
import { AGENTS } from './AgentCards';
import { CLOUD_PATH, CloudDiagram } from './CloudDiagram';
import { FLOW_STEPS, FlowDiagram } from './FlowDiagram';
import { HowOverview, SCENES } from './HowOverview';
import { OntologySection } from './OntologySection';
import recorded from '../../samples/recorded-restores.json';
import reading from '../../hero/hero-reading.json';
import { HERO } from '../../hero/heroData';
import { SLICE, UTAIYAR, VARI, VARI_PARALLEL } from './how-data';
import { mentionsBannedName } from '../../test/copyRules';

const TAMIL = /[஀-௿]/;

function mockReducedMotion(reduce: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((q: string) => ({ matches: reduce && q.includes('prefers-reduced-motion: reduce'), media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
}
/** An IntersectionObserver that reports every observed element as on screen at once. */
function mockInView() {
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(private cb: (e: { isIntersecting: boolean; target: Element }[]) => void) {}
      observe(el: Element) {
        this.cb([{ isIntersecting: true, target: el }]);
      }
      disconnect() {}
      unobserve() {}
    },
  );
}

describe('How it works: the page', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('opens with the animated overview, then the six sections, then the honest limits', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const ids = ['how-hero', 'how-agents', 'how-flow', 'how-ontology', 'how-models', 'how-cloud', 'how-people', 'how-limits'];
    const els = ids.map((id) => screen.getByTestId(id));
    for (let i = 1; i < els.length; i++) {
      expect(els[i - 1]!.compareDocumentPosition(els[i]!) & Node.DOCUMENT_POSITION_FOLLOWING, `${ids[i - 1]} before ${ids[i]}`).toBeTruthy();
    }
    expect(screen.getByRole('heading', { level: 2, name: 'The agents' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'The ontology' })).toBeInTheDocument();
  });

  it('has one compact card per agent with a real example; inputs, outputs and technique sit under "More"', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const cards = within(screen.getByTestId('agent-cards')).getAllByRole('listitem');
    expect(cards).toHaveLength(AGENTS.length);
    for (const a of AGENTS) {
      const card = screen.getByTestId(`agent-${a.key}`);
      expect(card).toHaveAttribute('id', a.anchor);
      const more = card.querySelector('details.how-more')!;
      expect(more, a.key).not.toBeNull();
      expect(within(more as HTMLElement).getByText('Takes')).toBeInTheDocument();
      expect(within(more as HTMLElement).getByText('Gives')).toBeInTheDocument();
      expect(more).not.toHaveAttribute('open');
      const ex = screen.getByTestId(`agent-ex-${a.key}`);
      expect(ex.querySelector('.bi-ta')?.textContent, a.key).toMatch(TAMIL);
      expect(ex.querySelector('.bi-iso')?.textContent, a.key).toBeTruthy();
    }
    // Recorded numbers, not invented ones.
    expect(screen.getByTestId('agent-ex-restorer')).toHaveTextContent('ப் (p) at 96%');
    expect(screen.getByTestId('agent-ex-restorer')).toHaveTextContent('matches the editors’ restoration');
    expect(screen.getByTestId('agent-ex-ngram')).toHaveTextContent('99%');
    expect(screen.getByTestId('agent-ex-check')).toHaveTextContent('15%, below the level of 41%');
    expect(screen.getByTestId('agent-retrieval')).toHaveTextContent('14,355 training-set lines');
    expect(screen.getByTestId('agent-ex-retrieval')).toHaveTextContent('vari-p-pāṭum');
    expect(screen.getByTestId('agent-tutor')).toHaveTextContent('Strands Graph');
    expect(screen.getByTestId('agent-tutor')).toHaveTextContent('Swarm');
    expect(screen.getByTestId('agent-decider')).toHaveTextContent('Not used for restoration');
  });

  it('states where the Strands Decider is and is not used, with the measured numbers', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const dec = screen.getByTestId('models-decider');
    expect(dec).toHaveTextContent('Used in lessons');
    expect(dec).toHaveTextContent('Not used for restoration');
    expect(dec).toHaveTextContent('39 times against 41');
    expect(dec).toHaveTextContent('13 of the 120 took longer than the 27-second limit');
    expect(screen.getByTestId('models-cal')).toHaveTextContent('fill level 41%');
    expect(screen.getByTestId('models-cal')).toHaveTextContent('(187 of 206)');
    expect(screen.getByTestId('models-route')).toHaveTextContent('296 of 413 test gaps used Opus');
    expect(screen.getByTestId('models-route')).toHaveTextContent('$0.006 per gap');
  });

  it('shows the cloud boxes verified in infra/, and a request travels along them while on screen', () => {
    vi.useFakeTimers();
    mockInView();
    try {
      renderApp(<CloudDiagram stepMs={500} />);
      const svg = screen.getByTestId('cloud-svg');
      const boxes = [...svg.querySelectorAll('[data-node]')].map((g) => [...g.querySelectorAll('text')].map((x) => x.textContent).join(' '));
      const all = boxes.join(' | ');
      for (const name of ['Amazon CloudFront', 'Amazon S3', 'Amazon API Gateway', 'AWS Lambda', 'Bedrock AgentCore Runtime', 'Amazon DynamoDB', 'Amazon Cognito', 'Amazon Bedrock', 'AWS Secrets Manager']) {
        expect(all, name).toContain(name);
      }
      expect(all).not.toMatch(/Neptune|OpenSearch|…/);
      const seen: string[] = [];
      for (let i = 0; i < CLOUD_PATH.length; i++) {
        act(() => {
          vi.advanceTimersByTime(500);
        });
        seen.push([...svg.querySelectorAll('[data-node].is-active')].map((n) => n.getAttribute('data-node')).join(','));
      }
      expect(seen).toEqual(CLOUD_PATH.map((hop) => hop.at(-1)));
    } finally {
      vi.useRealTimers();
    }
  });

  it('people in the loop: three steps to a reviewed reading, and the validation kit, honestly not yet run', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const p = screen.getByTestId('people');
    expect(p.querySelectorAll('.people-step')).toHaveLength(3);
    expect(p).toHaveTextContent('approve, edit or reject');
    expect(p).toHaveTextContent('no study has run yet');
    expect(screen.getByTestId('people-review')).toHaveAttribute('href', '/review');
  });

  it('honest limits come from benchmark/summary.json', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    expect(screen.getByTestId('lim-top1')).toHaveTextContent('63%');
    expect(screen.getByTestId('lim-top1')).toHaveTextContent('259 of 413');
    expect(screen.getByTestId('lim-fill')).toHaveTextContent('91%');
    expect(screen.getByTestId('lim-fill')).toHaveTextContent('187 of 206');
    expect(screen.getByTestId('lim-long')).toHaveTextContent('20%');
    expect(screen.getByTestId('how-results')).toHaveAttribute('href', '/benchmark');
  });

  it('renders in Tamil with Tamil headings', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works', lang: 'ta' });
    expect(screen.getByRole('heading', { level: 2, name: 'முகவர்கள்' })).toBeInTheDocument();
    expect(screen.getByTestId('agent-ex-restorer')).toHaveTextContent('பதிப்பாசிரியர்களின் மீட்டமைப்புடன் பொருந்துகிறது');
    expect(screen.getByTestId('hx-scene-reader')).toHaveTextContent('சோழர் காலத் தமிழ்');
    expect(screen.getByTestId('lim-top1')).toHaveTextContent('413-இல் 259');
  });
});

describe('The animated overview', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
  const gap = (reading as unknown as { restore: { gaps: { decision: string; abstain_below: number; best: { ta: string; confidence: number } }[] } }).restore.gaps[0]!;

  it('shows the real run: letters with confidences, the gap, the restorer, the check, the words and the tutor graph', () => {
    renderApp(<HowOverview />);
    // The band marks every letter of the line; the one under the Reader's cut-off is the gap.
    expect(screen.getByTestId('hx-stage').querySelectorAll('.hx-box')).toHaveLength(HERO.boxes[HERO.gaps[0]!.r]!.length);
    expect(screen.getByTestId('hx-box-gap')).toBeInTheDocument();
    expect(screen.getByTestId('hx-scene-reader')).toHaveTextContent(`Chola-era Tamil · ${HERO.letters} letters · average 65%`);
    expect(screen.getByTestId('hx-scene-reader')).toHaveTextContent('Under 50%: marked [?]');
    const restorer = screen.getByTestId('hx-scene-restorer');
    expect(restorer).toHaveTextContent('14,355 training lines');
    expect(restorer).toHaveTextContent('Sonnet 4.6 → Opus 4.6');
    expect(restorer).toHaveTextContent(`${gap.best.ta} ${Math.round(gap.best.confidence * 100)}%`);
    // The same gap as hero-reading.json's Restorer run (deployed config): left open below its calibrated level.
    expect(gap.decision).toBe('abstain');
    const open = screen.getByTestId('hx-gauge-this');
    expect(open).toHaveTextContent('8%');
    expect(open).toHaveTextContent(`level ${Math.round(gap.abstain_below * 100)}%`);
    expect(open).toHaveTextContent('left open');
    const fill = screen.getByTestId('hx-gauge-other');
    expect(fill).toHaveTextContent('96%');
    expect(fill).toHaveTextContent('level 41%');
    expect(fill).toHaveTextContent('filled');
    expect(screen.getByTestId('hx-scene-check')).toHaveTextContent('noisy-OR pre-rank + Platt calibration');
    const interp = screen.getByTestId('hx-scene-interp');
    expect(interp).toHaveTextContent('குளம்');
    expect(interp).toHaveTextContent('tank / pond');
    expect(interp).toHaveTextContent('75%');
    for (const w of HERO.words.filter((x) => (x.c ?? 0) < HERO.letterCut)) expect(interp.querySelector('.hx-words')).not.toHaveTextContent(w.ta);
    const tutor = screen.getByTestId('hx-scene-tutor');
    for (const s of ['restore', 'lesson_builder', 'Swarm: Tutor ⇄ Assessor', 'Strands Decider: move on · repeat · hint']) expect(tutor).toHaveTextContent(s);
  });

  it('plays the scenes in order, loops, and stops when a station is chosen or Pause is pressed', () => {
    vi.useFakeTimers();
    renderApp(<HowOverview sceneMs={1000} />);
    const stage = screen.getByTestId('hx-stage');
    expect(stage).toHaveAttribute('data-scene', 'stone');
    const seen: string[] = [];
    for (let i = 0; i < SCENES.length; i++) {
      seen.push(stage.getAttribute('data-scene')!);
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(seen).toEqual([...SCENES]);
    expect(stage).toHaveAttribute('data-scene', 'stone');
    expect(screen.getByTestId('hx-scene-stone')).toHaveClass('is-on');
    expect(screen.getByTestId('hx-scene-reader')).toHaveAttribute('aria-hidden', 'true');
    fireEvent.click(screen.getByTestId('hx-step-check'));
    expect(stage).toHaveAttribute('data-scene', 'check');
    expect(screen.getByTestId('hx-step-check')).toHaveAttribute('aria-current', 'step');
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(stage).toHaveAttribute('data-scene', 'check');
    expect(screen.getByTestId('hx-play')).toHaveTextContent('Play');
    fireEvent.click(screen.getByTestId('hx-play'));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(stage).toHaveAttribute('data-scene', 'interp');
  });

  it('reduced motion: a composed still frame with every scene, and no play control', () => {
    mockReducedMotion(true);
    renderApp(<HowOverview />);
    expect(screen.getByTestId('hx-stage')).toHaveClass('hx-still');
    for (const k of SCENES) expect(screen.getByTestId(`hx-scene-${k}`)).not.toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByTestId('hx-play')).toBeNull();
  });

  it('is in Tamil when the app is', () => {
    renderApp(<HowOverview />, { lang: 'ta' });
    expect(screen.getByTestId('hx-scene-check')).toHaveTextContent('திறந்து விடப்பட்டது');
    expect(screen.getByTestId('hx-step-reader')).toHaveTextContent('வாசிப்பான்');
  });
});

describe('Flow diagram stepper', () => {
  afterEach(() => vi.useRealTimers());

  it('starts idle, steps forward and back, and highlights each hop', async () => {
    renderApp(<FlowDiagram autoPlay={false} />);
    const caption = screen.getByTestId('flow-caption');
    expect(caption).toHaveTextContent(enHow['hw.flowIdle']);
    expect(screen.getByTestId('flow-prev')).toBeDisabled();
    await userEvent.click(screen.getByTestId('flow-next'));
    expect(caption).toHaveTextContent(enHow['hw.s1']);
    expect(screen.getByTestId('flow-count')).toHaveTextContent(`Step 1 of ${FLOW_STEPS.length}`);
    const svg = screen.getByTestId('flow-svg');
    expect(svg.querySelector('[data-node="reader"]')).toHaveClass('is-active');
    expect(svg.querySelector('[data-node="expert"]')).toHaveClass('is-dim');
    await userEvent.click(screen.getByTestId('flow-next'));
    expect(caption).toHaveTextContent(enHow['hw.s2']);
    expect(svg.querySelector('[data-edge="e-reader-reread"]')).toHaveClass('is-active');
    expect(svg.querySelector('[data-node="photo"]')).toHaveClass('is-done');
    await userEvent.click(screen.getByTestId('flow-prev'));
    expect(caption).toHaveTextContent(enHow['hw.s1']);
  });

  it('starts playing by itself once on screen, and walks every hop including the escalation, abstain and expert-review branches', () => {
    vi.useFakeTimers();
    renderApp(<FlowDiagram intervalMs={1000} />);
    const play = screen.getByTestId('flow-play');
    expect(play).toHaveTextContent('Pause');
    const seen: string[] = [screen.getByTestId('flow-caption').textContent ?? ''];
    for (let i = 1; i < FLOW_STEPS.length; i++) {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      seen.push(screen.getByTestId('flow-caption').textContent ?? '');
    }
    expect(seen).toEqual(FLOW_STEPS.map((s) => enHow[s.caption as keyof typeof enHow]));
    expect(seen.some((c) => c.startsWith('Escalation'))).toBe(true);
    expect(seen.some((c) => c.startsWith('Abstain'))).toBe(true);
    expect(seen.at(-1)).toMatch(/^Expert review/);
    expect(screen.getByTestId('flow-play')).toHaveTextContent('Play the flow');
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByTestId('flow-count')).toHaveTextContent(`Step ${FLOW_STEPS.length} of ${FLOW_STEPS.length}`);
  });

  it('does not start by itself under reduced motion', () => {
    mockReducedMotion(true);
    try {
      renderApp(<FlowDiagram />);
      expect(screen.getByTestId('flow-play')).toHaveTextContent('Play the flow');
      expect(screen.getByTestId('flow-count')).toHaveTextContent('');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('lists every step as text for readers who prefer it', () => {
    renderApp(<FlowDiagram autoPlay={false} />);
    expect(screen.getByText('The steps as a list').closest('details')!.querySelectorAll('li')).toHaveLength(FLOW_STEPS.length);
  });
});

describe('Ontology section', () => {
  it('shows a real train-only slice; choosing an entry shows its link and the stones behind it', async () => {
    renderApp(<OntologySection />);
    expect(screen.getByTestId('onto-detail')).toHaveTextContent('Rājarāja I Cōḻa');
    expect(screen.getByTestId('onto-detail')).toHaveTextContent('Wikidata Q2128757');
    await userEvent.click(screen.getByTestId('onto-node-ez:measure/kani'));
    const d = screen.getByTestId('onto-detail');
    expect(d).toHaveTextContent('காணி');
    expect(d).toHaveTextContent('Named on the same stones as the king');
    const kani = SLICE.edges.find((e) => e.to === 'ez:measure/kani')!;
    expect(d).toHaveTextContent(`Named together on ${kani.n} stones`);
    expect(within(d).getByRole('link', { name: new RegExp(kani.evidence![0]!) })).toHaveAttribute('href', `https://dharmalekha.info/texts/${kani.evidence![0]}`);
    await userEvent.click(screen.getByTestId('onto-node-ez:formula/tirumakal-pola'));
    expect(screen.getByTestId('onto-detail')).toHaveTextContent('Royal praise (meykkīrtti) of this king');
  });

  it('gives counts by kind as bars, the storage honestly, the hint examples and the measured (null) effect, with credits', () => {
    renderApp(<OntologySection />);
    expect(screen.getByTestId('onto-count-ruler')).toHaveTextContent('42');
    expect(screen.getByTestId('onto-count-temple')).toHaveTextContent('139');
    expect(screen.getByTestId('onto-count-place')).toHaveTextContent('357');
    expect(screen.getByTestId('onto-store')).toHaveTextContent('27 classes · 21 relations · 1,958 entries');
    expect(screen.getByTestId('onto-coa')).toHaveTextContent('S3 Vectors + FalkorDB');
    expect(screen.getByTestId('onto-coa')).toHaveTextContent('prepared, not running');
    expect(screen.getByTestId('onto-store')).toHaveTextContent('862 of 1,193 editions used');
    expect(screen.getByTestId('onto-hints')).toHaveTextContent('measure: vari');
    expect(screen.getByTestId('onto-hints')).toHaveTextContent('title: uṭaiyār');
    expect(screen.getByTestId('onto-effect')).toHaveTextContent('Not measurably, yet');
    expect(screen.getByTestId('onto-effect')).toHaveTextContent('6.3% of held-out test gaps (16 of 253)');
    expect(screen.getByTestId('onto-credit')).toHaveTextContent('CC BY-SA 4.0');
    expect(screen.getByTestId('onto-credit')).toHaveTextContent('CC0');
  });
});

describe('Home agent chips', () => {
  it('links each helper to its anchor on /how-it-works, and every anchor exists there', () => {
    const { unmount } = renderApp(<AgentChips />);
    const links = within(screen.getByTestId('agent-chips')).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Reader', 'Restorer', 'Ontology', 'Retrieval', 'Strands Decider', 'Interpreter', 'Tutor', 'Expert review']);
    const hashes = links.map((l) => l.getAttribute('href')!.split('#')[1]!);
    for (const l of links) expect(l.getAttribute('href')).toMatch(/^\/how-it-works#/);
    unmount();
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    for (const h of hashes) expect(document.getElementById(h), h).not.toBeNull();
  });
});

describe('copy rules for the new strings', () => {
  it('never says "correct", "experimental", the banned name, "Strands AI" or "AWS AI", and says "built with Strands Agents"', () => {
    const bad = Object.entries({ ...enHow, ...taHow }).filter(([, v]) => /\bcorrect\b|experimental|strands ai\b|aws ai\b|1,100/i.test(v) || mentionsBannedName(v));
    expect(bad).toEqual([]);
    expect(enHow['hw.agentsLede']).toContain('built with Strands Agents');
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    expect(document.body.textContent).not.toMatch(/\bcorrect\b|experimental|strands ai\b|aws ai\b/i);
    expect(mentionsBannedName(document.body.textContent)).toBe(false);
  });

  it('keeps the copy short: the English strings for the page stay under 1,400 words', () => {
    const words = Object.values(enHow).join(' ').split(/\s+/).filter(Boolean).length;
    expect(words).toBeLessThan(1400);
  });
});

describe('diagram labels fit their boxes', () => {
  for (const lang of ['en', 'ta'] as const) {
    it(`no label or caption is cut short in the flow and cloud diagrams (${lang})`, () => {
      renderApp(
        <>
          <FlowDiagram autoPlay={false} />
          <CloudDiagram />
        </>,
        { lang },
      );
      const cut = [...document.querySelectorAll('svg.dg text')].map((x) => x.textContent ?? '').filter((x) => x.endsWith('…'));
      expect(cut).toEqual([]);
    });
  }
});

describe('copied recordings match samples/recorded-restores.json', () => {
  it('the vari and uṭaiyār gaps are exactly as recorded', () => {
    const rec = (recorded as unknown as { samples: Record<string, { response: { gaps: { decision: string; chosen: number; candidates: Record<string, unknown>[] }[] } }> }).samples;
    for (const g of [VARI, UTAIYAR]) {
      const gap = rec[g.sample]!.response.gaps[0]!;
      const top = gap.candidates[gap.chosen]! as { text: string; text_tamil: string; confidence: number; sources: string[]; features: { ngram_probability: number }; ontology_hints: unknown[]; parallels: { inscription_id: string; line_n: string; snippet: string }[] };
      expect(gap.decision).toBe(g.decision);
      expect({ text: top.text, text_tamil: top.text_tamil, confidence: top.confidence, sources: top.sources, ngram_probability: top.features.ngram_probability }).toEqual({
        text: g.top.text, text_tamil: g.top.text_tamil, confidence: g.top.confidence, sources: g.top.sources, ngram_probability: g.top.ngram_probability,
      });
      for (const h of g.top.ontology_hints) expect(top.ontology_hints).toContainEqual(h);
      if (g === VARI) {
        expect(top.parallels[0]!.inscription_id).toBe(VARI_PARALLEL.id);
        expect(top.parallels[0]!.line_n).toBe(VARI_PARALLEL.line);
        expect(top.parallels[0]!.snippet).toContain(VARI_PARALLEL.iso);
      }
    }
  });
});
