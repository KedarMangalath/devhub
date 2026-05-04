import React, { useMemo } from 'react';
import Navbar from '../components/shared/Navbar';
import MetricCard from '../components/shared/MetricCard';
import GeographicHeatmap from '../components/director/GeographicHeatmap';
import RiskProfileTable from '../components/director/RiskProfileTable';
import { dashboardMetrics } from '../mockData';
import { BarChart3, ShieldAlert, Users, Activity } from 'lucide-react';

export default function DirectorAnalytics() {
  // Process metrics for the top row, ensuring a robust fallback if mock data is sparse
  const directorMetrics = useMemo(() => {
    const metrics = dashboardMetrics?.filter(m => m.role === 'Director') || [];
    
    if (metrics.length >= 4) return metrics.slice(0, 4);
    
    // Fallback rich data to guarantee a fully populated UI on first load
    return [
      { id: 'm1', metric_name: 'Total Active Cases', value: '1,248', trend_percentage: '+12%' },
      { id: 'm2', metric_name: 'High Risk Departments', value: '4', trend_percentage: '-1' },
      { id: 'm3', metric_name: 'Avg Resolution Time', value: '14 Days', trend_percentage: '-2 Days' },
      { id: 'm4', metric_name: 'Citizen Trust Score', value: '92/100', trend_percentage: '+5%' },
    ];
  }, []);

  const metricIcons = [Activity, ShieldAlert, BarChart3, Users];

  // Mock data for the CSS-based trend chart
  const trendData = useMemo(() => [
    { label: 'Week 1', short: 'W1', value: 320 },
    { label: 'Week 2', short: 'W2', value: 450 },
    { label: 'Week 3', short: 'W3', value: 280 },
    { label: 'Week 4', short: 'W4', value: 510 },
    { label: 'Week 5', short: 'W5', value: 390 },
    { label: 'Week 6', short: 'W6', value: 420 },
  ], []);
  
  const maxTrendValue = Math.max(...trendData.map(d => d.value));

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col font-sans text-[#0F172A] selection:bg-vacb-700/20 selection:text-vacb-700">
      <Navbar />

      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex flex-col gap-8">
        
        {/* Page Header */}
        <header>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Director Analytics Overview</h1>
          <p className="text-sm text-slate-500 mt-1">Statewide grievance monitoring, department risk assessment, and SLA tracking.</p>
        </header>

        {/* Top Row: Strategic KPIs */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {directorMetrics.map((metric, idx) => {
            const Icon = metricIcons[idx % metricIcons.length];
            return (
              <MetricCard
                key={metric.id || idx}
                title={metric.metric_name}
                value={metric.value}
                trend={metric.trend_percentage}
                icon={Icon}
              />
            );
          })}
        </section>

        {/* Middle Row: Heatmap & Trend Chart */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Geographic Heatmap (Takes up 2/3 width on large screens) */}
          <div className="lg:col-span-2 h-[420px]">
            <GeographicHeatmap />
          </div>

          {/* Mock Trend Chart (Takes up 1/3 width) */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col h-[420px]">
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-vacb-700" />
                Filing Volume Trend
              </h3>
              <p className="text-sm text-slate-500 mt-1">Weekly complaint submissions across all districts (6-week view).</p>
            </div>

            <div className="flex-1 flex flex-col justify-end relative mt-2">
              {/* Background Grid Lines */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none pb-6">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="w-full border-t border-slate-100 border-dashed h-0"></div>
                ))}
              </div>

              {/* Bars */}
              <div className="flex items-end justify-between gap-2 h-full pb-2 z-10">
                {trendData.map((item, i) => {
                  const heightPct = (item.value / maxTrendValue) * 100;
                  return (
                    <div key={i} className="flex flex-col items-center gap-2 w-full group h-full justify-end">
                      <div className="w-full relative flex items-end justify-center h-full">
                        <div
                          className="w-3/4 sm:w-4/5 bg-vacb-700/80 group-hover:bg-vacb-700 transition-all duration-300 rounded-t-sm relative"
                          style={{ height: `${heightPct}%` }}
                        >
                          {/* Tooltip on hover */}
                          <div className="opacity-0 group-hover:opacity-100 absolute -top-10 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-xs py-1.5 px-2.5 rounded shadow-lg transition-opacity whitespace-nowrap pointer-events-none">
                            <span className="font-semibold">{item.value}</span> cases
                            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800"></div>
                          </div>
                        </div>
                      </div>
                      <span className="text-xs font-medium text-slate-500" title={item.label}>
                        {item.short}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        {/* Bottom Row: Risk Profile Table */}
        <section className="flex-1">
          <RiskProfileTable />
        </section>

      </main>
    </div>
  );
}
