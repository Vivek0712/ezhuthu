import { act, fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { enHow } from '../../i18n/strings-how';
import { HowItWorksPage } from '../../pages/HowItWorksPage';
import { renderApp } from '../../test/render';
import { AgentChips } from './AgentChips';
import { AGENTS } from './AgentCards';
import { CloudDiagram } from './CloudDiagram';
import { FLOW_STEPS, FlowDiagram } from './FlowDiagram';
import { OntologySection } from './OntologySection';
import recorded from '../../samples/recorded-restores.json';
import { SLICE, UTAIYAR, VARI, VARI_PARALLEL } from './how-data';

const TAMIL = /[஀-௿]/;

describe('How it works: the full explanation', () => {
  it('renders the six new sections after the walk-through and before the honest limits', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const ids = ['worked-example', 'how-agents', 'how-flow', 'how-ontology', 'how-models', 'how-cloud', 'how-people', 'how-limits'];
    const els = ids.map((id) => screen.getByTestId(id));
    for (let i = 1; i < els.length; i++) {
      expect(els[i - 1]!.compareDocumentPosition(els[i]!) & Node.DOCUMENT_POSITION_FOLLOWING, `${ids[i - 1]} before ${ids[i]}`).toBeTruthy();
    }
    expect(screen.getByRole('heading', { level: 2, name: 'The agents' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'The ontology' })).toBeInTheDocument();
  });

  it('has one card per agent, each with inputs, outputs and a real example in Tamil script and English letters', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const cards = within(screen.getByTestId('agent-cards')).getAllByRole('listitem');
    expect(cards).toHaveLength(AGENTS.length);
    for (const a of AGENTS) {
      const card = screen.getByTestId(`agent-${a.key}`);
      expect(card).toHaveAttribute('id', a.anchor);
      expect(within(card).getByText('Takes')).toBeInTheDocument();
      expect(within(card).getByText('Gives')).toBeInTheDocument();
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
    expect(screen.getByTestId('agent-tutor')).toHaveTextContent('Strands Swarm');
  });

  it('states where the Strands Decider is and is not used, with the measured numbers', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const dec = screen.getByTestId('models-decider');
    expect(dec).toHaveTextContent('Used in lessons');
    expect(dec).toHaveTextContent('Not used for restoration');
    expect(dec).toHaveTextContent('39 times against 41');
    expect(dec).toHaveTextContent('13 of the 120 gaps took longer than the 27-second limit');
    expect(screen.getByTestId('models-cal')).toHaveTextContent('41% when Sonnet answered, 49% when Opus did');
    expect(screen.getByTestId('models-cal')).toHaveTextContent('(187 of 206)');
    expect(screen.getByTestId('models-route')).toHaveTextContent('296 used Opus (291 sent straight to it, 5 after Sonnet)');
    // The pipeline's decision step is the calibrated check, not the Decider.
    expect(screen.getByTestId('pipe-decider')).toHaveTextContent('Confidence check');
  });

  it('shows the cloud boxes verified in infra/', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const svg = screen.getByTestId('cloud-svg');
    const boxes = [...svg.querySelectorAll('[data-node]')].map((g) => [...g.querySelectorAll('text')].map((x) => x.textContent).join(' '));
    const all = boxes.join(' | ');
    for (const name of ['Amazon CloudFront', 'Amazon S3', 'Amazon API Gateway', 'AWS Lambda', 'Bedrock AgentCore Runtime', 'Amazon DynamoDB', 'Amazon Cognito', 'Amazon Bedrock', 'AWS Secrets Manager']) {
      expect(all, name).toContain(name);
    }
    expect(all).not.toMatch(/Neptune|OpenSearch|…/);
  });

  it('people in the loop: review queue and the validation kit, honestly not yet run', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works' });
    const p = screen.getByTestId('people');
    expect(p).toHaveTextContent('approve, edit or reject');
    expect(p).toHaveTextContent('No study has run yet');
    expect(screen.getByTestId('people-review')).toHaveAttribute('href', '/review');
  });

  it('renders in Tamil with Tamil headings', () => {
    renderApp(<HowItWorksPage />, { route: '/how-it-works', lang: 'ta' });
    expect(screen.getByRole('heading', { level: 2, name: 'முகவர்கள்' })).toBeInTheDocument();
    expect(screen.getByTestId('agent-ex-restorer')).toHaveTextContent('பதிப்பாசிரியர்களின் மீட்டமைப்புடன் பொருந்துகிறது');
  });
});

describe('Flow diagram stepper', () => {
  afterEach(() => vi.useRealTimers());

  it('starts idle, steps forward and back, and highlights each hop', async () => {
    renderApp(<FlowDiagram />);
    const caption = screen.getByTestId('flow-caption');
    expect(caption).toHaveTextContent('Press “Play the flow”');
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

  it('"Play the flow" walks every hop, including the escalation, abstain and expert-review branches, then stops', () => {
    vi.useFakeTimers();
    renderApp(<FlowDiagram intervalMs={1000} />);
    const play = screen.getByTestId('flow-play');
    expect(play).toHaveTextContent('Play the flow');
    fireEvent.click(play);
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

  it('lists every step as text for readers who prefer it', () => {
    renderApp(<FlowDiagram />);
    expect(screen.getByText('Read the steps as a list').closest('details')!.querySelectorAll('li')).toHaveLength(FLOW_STEPS.length);
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

  it('gives counts by kind, the storage honestly, the hint examples and the measured (null) effect, with credits', () => {
    renderApp(<OntologySection />);
    expect(screen.getByTestId('onto-count-ruler')).toHaveTextContent('42');
    expect(screen.getByTestId('onto-count-temple')).toHaveTextContent('139');
    expect(screen.getByTestId('onto-store')).toHaveTextContent('27 classes, 21 relations and 1,958 named entries');
    expect(screen.getByTestId('onto-store')).toHaveTextContent('has not been run');
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
  it('never says "correct", "experimental" or Aivar, and says "built with Strands Agents"', () => {
    const bad = Object.entries(enHow).filter(([, v]) => /\bcorrect\b|experimental|aivar/i.test(v));
    expect(bad).toEqual([]);
    expect(enHow['hw.agentsLede']).toContain('built with Strands Agents');
  });
});

describe('diagram labels fit their boxes', () => {
  for (const lang of ['en', 'ta'] as const) {
    it(`no label or caption is cut short in the flow and cloud diagrams (${lang})`, () => {
      renderApp(
        <>
          <FlowDiagram />
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
