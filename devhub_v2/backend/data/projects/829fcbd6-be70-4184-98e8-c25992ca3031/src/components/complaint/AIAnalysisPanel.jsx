import React from 'react';
import { BrainCircuit, AlertTriangle, CheckCircle } from 'lucide-react';

export default function AIAnalysisPanel({ score = 82, insights = [] }) {
  // Determine color based on score
  const getScoreColor = (s) => {
    if (s >= 80) return 'text-emerald-600 bg-emerald-500';
    if (s >= 50) return 'text-amber-600 bg-amber-500';
    return 'text-rose-600 bg-rose-500';
  };

  const getScoreBg = (s) => {
    if (s >= 80) return 'bg-emerald-100 dark:bg-emerald-950/30';
    if (s >= 50) return 'bg-amber-100 dark:bg-amber-950/30';
    return 'bg-rose-100 dark:bg-rose-950/30';
  };

  const scoreColors = getScoreColor(score).split(' ');
  const textColor = scoreColors[0];
  const barColor = scoreColors[1];
  const trackColor = getScoreBg(score);

  // Default insights if none provided to ensure UI is never empty
  const displayInsights = insights && insights.length > 0 ? insights : [
    { id: 'ins-1', type: 'success', text: 'Evidence metadata (GPS, timestamps) strongly correlates with the reported incident timeline.' },
    { id: 'ins-2', type: 'warning', text: 'Anomaly detected: 3 similar complaints filed against this specific department node in the last 14 days.' },
    { id: 'ins-3', type: 'success', text: 'NLP analysis indicates high factual consistency and low emotional exaggeration in the narrative.' }
  ];

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="p-5 border-b border-border bg-secondary/40 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-primary/10 rounded-md">
            <BrainCircuit className="w-5 h-5 text-primary" />
          </div>
          <h3 className="font-display font-semibold text-foreground text-lg tracking-tight">
            AI Credibility Analysis
          </h3>
        </div>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
          Auto-generated
        </span>
      </div>

      <div className="p-6 flex-1 flex flex-col gap-8">
        {/* Score Section */}
        <div>
          <div className="flex justify-between items-end mb-3">
            <span className="font-body text-sm text-muted-foreground font-medium uppercase tracking-wider">
              Confidence Score
            </span>
            <div className="flex items-baseline gap-1">
              <span className={`font-display text-4xl font-bold ${textColor}`}>
                {score}
              </span>
              <span className="text-muted-foreground text-sm font-medium">/100</span>
            </div>
          </div>
          
          {/* Progress Bar */}
          <div className={`h-3 w-full rounded-full overflow-hidden ${trackColor} shadow-inner`}>
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-out ${barColor}`}
              style={{ width: `${score}%` }}
            />
          </div>
          
          <p className="font-body text-sm text-muted-foreground mt-3 leading-relaxed">
            {score >= 80 ? 'High probability of factual accuracy based on cross-referenced evidence and historical patterns.' :
             score >= 50 ? 'Moderate credibility. Manual review of attached evidence is highly recommended.' :
             'Low credibility score. Potential inconsistencies or lack of verifiable evidence detected.'}
          </p>
        </div>

        {/* Insights List */}
        <div className="flex-1">
          <h4 className="font-body text-sm font-semibold text-foreground mb-4 uppercase tracking-wider flex items-center gap-2">
            Key Flags & Insights
            <span className="flex-1 h-px bg-border"></span>
          </h4>
          <ul className="space-y-3">
            {displayInsights.map((insight) => (
              <li 
                key={insight.id} 
                className="flex items-start gap-3 p-3.5 rounded-lg bg-secondary/30 border border-border/50 hover:bg-secondary/50 transition-colors"
              >
                <div className="mt-0.5 flex-shrink-0">
                  {insight.type === 'warning' ? (
                    <AlertTriangle className="w-4.5 h-4.5 text-amber-500" />
                  ) : insight.type === 'danger' ? (
                    <AlertTriangle className="w-4.5 h-4.5 text-rose-500" />
                  ) : (
                    <CheckCircle className="w-4.5 h-4.5 text-emerald-500" />
                  )}
                </div>
                <p className="font-body text-sm text-foreground leading-relaxed">
                  {insight.text}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}