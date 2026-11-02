import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import '../../styles/how.css';
import { useAgentName, type AgentKey } from './AgentCards';

/** Home: one compact line of chips, each linking to that helper's card (or the ontology section) on /how-it-works. */
const CHIPS: { key: AgentKey | 'ontologySection'; to: string; label?: MessageKey }[] = [
  { key: 'reader', to: '/how-it-works#agent-reader' },
  { key: 'restorer', to: '/how-it-works#agent-restorer' },
  { key: 'ontologySection', to: '/how-it-works#how-ontology' },
  { key: 'retrieval', to: '/how-it-works#agent-retrieval', label: 'hw.retrieval.chip' },
  { key: 'decider', to: '/how-it-works#agent-decider' },
  { key: 'interpreter', to: '/how-it-works#agent-interpreter' },
  { key: 'tutor', to: '/how-it-works#agent-tutor' },
  { key: 'review', to: '/how-it-works#agent-review' },
];

export function AgentChips() {
  const { t } = useI18n();
  const name = useAgentName();
  return (
    <nav className="agent-chips" aria-label={t('hw.chipsLabel')} data-testid="agent-chips">
      <span className="agent-chips-k">{t('hw.chipsLabel')}</span>
      <ul>
        {CHIPS.map((c) => (
          <li key={c.key}>
            <Link to={c.to} className="agent-chip" data-testid={`chip-${c.key}`}>
              {c.label ? t(c.label) : c.key === 'ontologySection' ? t('hw.ontology.name') : name(c.key)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
