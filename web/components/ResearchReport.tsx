import { BookOpen, ArrowDownToLine } from 'lucide-react';
import source from '../content/report-source.md?raw';

function inline(text: string) {
  return text.split(/(\[[^\]]+\]\(https?:\/\/[^)]+\))/g).map((part, i) => {
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    return link ? (
      <a key={i} href={link[2]} target="_blank" rel="noreferrer">
        {link[1]}
      </a>
    ) : (
      part
    );
  });
}
const sections = source.split('\n## ');
const title = sections[0].split('\n')[0].slice(2);
const parts = sections.slice(1).map((section, i) => ({
  id: `research-${i + 1}`,
  heading: section.split('\n')[0],
  body: section.slice(section.indexOf('\n') + 1),
}));
function paragraphs(text: string) {
  return text
    .trim()
    .split(/\n\s*\n/)
    .map((p, i) =>
      p.startsWith('- ') ? (
        <ul key={i}>
          {p.split('\n').map((line, j) => (
            <li key={j}>{inline(line.replace(/^- /, ''))}</li>
          ))}
        </ul>
      ) : (
        <p key={i}>{inline(p.replace(/\n/g, ' '))}</p>
      ),
    );
}
export default function ResearchReport() {
  return (
    <main className="content-page research-dossier">
      <header className="dossier-hero">
        <div className="eyebrow">
          <BookOpen size={15} /> RESEARCH & METHODS · REVIEWED 08 SEP 2026
        </div>
        <h1>{title}</h1>
        <p>
          Scientific methods, real evidence, and a candid path to INCOIS
          deployment.
        </p>
        <div className="dossier-facts">
          <span>1,001 matched real levels</span>
          <span>5 evidence workflows</span>
          <span>Primary sources throughout</span>
        </div>
        <button className="secondary-button" onClick={() => window.print()}>
          <ArrowDownToLine size={15} /> Print / save research dossier
        </button>
      </header>
      <div className="dossier-layout">
        <nav aria-label="Research contents">
          <span className="eyebrow">IN THIS DOSSIER</span>
          {parts.map((p) => (
            <a href={`#${p.id}`} key={p.id}>
              {p.heading}
            </a>
          ))}
        </nav>
        <article>
          <div className="dossier-scope">
            {paragraphs(sections[0].split('\n').slice(2).join('\n'))}
          </div>
          {parts.map((p, i) => (
            <section id={p.id} key={p.id}>
              <span className="number-label">
                {String(i + 1).padStart(2, '0')} / RESEARCH
              </span>
              <h2>{p.heading}</h2>
              {paragraphs(p.body)}
            </section>
          ))}
        </article>
      </div>
    </main>
  );
}
