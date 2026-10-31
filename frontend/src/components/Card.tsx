import type { ReactNode } from "react";

interface CardProps {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
}

/** Titled panel used for every dashboard section, so headings and spacing stay consistent. */
export function Card({ title, subtitle, actions, children, id }: CardProps) {
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section className="card" aria-labelledby={headingId}>
      <header className="card__header">
        <div>
          <h2 id={headingId} className="card__title">
            {title}
          </h2>
          {subtitle && <p className="card__subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="card__actions">{actions}</div>}
      </header>
      {children}
    </section>
  );
}
