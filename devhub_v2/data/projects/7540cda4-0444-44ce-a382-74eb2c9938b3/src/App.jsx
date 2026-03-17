const highlights = [
  {
    title: 'Working skeleton',
    description: 'This project was generated with a real runnable React starter so you can iterate immediately.',
  },
  {
    title: 'Chat-driven edits',
    description: 'Ask DevHub to change components, layout, copy, or interactions and it can write those files for you.',
  },
  {
    title: 'Feature pipeline',
    description: 'Track larger work items through planning, implementation, testing, and review.',
  },
];

export default function App() {
  return (
    <div className="page-shell">
      <section className="hero-card">
        <span className="eyebrow">DevHub React Starter</span>
        <h1>Starter UI</h1>
        <p className="description">A generated React app</p>
        <div className="hero-actions">
          <button type="button">Create a feature</button>
          <button type="button" className="secondary">Update the UI with chat</button>
        </div>
      </section>

      <section className="highlight-grid">
        {highlights.map((item) => (
          <article key={item.title} className="highlight-card">
            <span className="pill">{item.title}</span>
            <p>{item.description}</p>
          </article>
        ))}
      </section>

      <section className="status-card">
        <div>
          <span className="eyebrow">Starter Status</span>
          <h2>Ready for code changes</h2>
          <p>Run the app, keep the preview open, and evolve this skeleton through feature additions or direct chat instructions.</p>
        </div>
        <div className="terminal-card">
          <p>$ npm install</p>
          <p>$ npm run dev</p>
          <p>Server ready on http://127.0.0.1:4173</p>
        </div>
      </section>
    </div>
  );
}
