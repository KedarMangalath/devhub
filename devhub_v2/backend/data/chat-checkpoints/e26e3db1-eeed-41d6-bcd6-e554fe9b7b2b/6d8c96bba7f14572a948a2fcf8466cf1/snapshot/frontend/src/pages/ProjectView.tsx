export default function ProjectView({ activeTab, tabs }: any) {
  return (
    <aside>
      <div className="hidden lg:block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 px-3">Views</div>
      {tabs.map((tab: any) => (
        <button
          key={tab.id}
          className={`shrink-0 lg:w-full flex items-center gap-3 px-3 py-3 rounded-2xl text-left transition-all whitespace-nowrap ${activeTab === tab.id ? 'bg-black text-white shadow-[0_18px_38px_rgba(15,23,42,0.18)]' : 'border border-transparent text-slate-600 hover:bg-white hover:border-black/5'}`}
        >
          <span className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-[11px] font-semibold ${activeTab === tab.id ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-500'}`}>{tab.icon}</span>
          <span className={`hidden lg:block truncate text-[10px] ${activeTab === tab.id ? 'text-white/70' : 'text-slate-400'}`}>{tab.helper}</span>
        </button>
      ))}
    </aside>
  );
}