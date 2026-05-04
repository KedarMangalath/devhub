import React, { useState, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, Calendar, AlertCircle, Info } from 'lucide-react';

// Fallback rich mock data to ensure zero empty states if props are missing
const defaultTrendData = [
  { month: 'Jan', actual: 420, predicted: null, lowerBound: null, upperBound: null },
  { month: 'Feb', actual: 380, predicted: null, lowerBound: null, upperBound: null },
  { month: 'Mar', actual: 450, predicted: null, lowerBound: null, upperBound: null },
  { month: 'Apr', actual: 490, predicted: null, lowerBound: null, upperBound: null },
  { month: 'May', actual: 510, predicted: null, lowerBound: null, upperBound: null },
  { month: 'Jun', actual: 480, predicted: 480, lowerBound: 480, upperBound: 480 }, // Connection point
  { month: 'Jul', actual: null, predicted: 520, lowerBound: 490, upperBound: 550 },
  { month: 'Aug', actual: null, predicted: 560, lowerBound: 510, upperBound: 610 },
  { month: 'Sep', actual: null, predicted: 590, lowerBound: 530, upperBound: 650 },
  { month: 'Oct', actual: null, predicted: 630, lowerBound: 550, upperBound: 710 },
  { month: 'Nov', actual: null, predicted: 610, lowerBound: 520, upperBound: 700 },
  { month: 'Dec', actual: null, predicted: 680, lowerBound: 580, upperBound: 780 },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card border border-border p-4 rounded-lg shadow-lg min-w-[200px]">
        <p className="font-display font-semibold text-foreground mb-2 border-b border-border pb-2">{label} 2024</p>
        <div className="space-y-2">
          {payload.map((entry, index) => {
            if (entry.value === null) return null;
            
            let labelName = entry.name;
            if (entry.name === 'actual') labelName = 'Historical Reports';
            if (entry.name === 'predicted') labelName = 'AI Forecast';
            if (entry.name === 'upperBound') labelName = 'Upper Confidence';
            if (entry.name === 'lowerBound') labelName = 'Lower Confidence';

            return (
              <div key={index} className="flex justify-between items-center text-sm">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <span 
                    className="w-2 h-2 rounded-full" 
                    style={{ backgroundColor: entry.color }}
                  />
                  {labelName}
                </span>
                <span className="font-medium text-foreground">{entry.value}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  return null;
};

export default function PredictiveTrendChart({ data = defaultTrendData }) {
  const [timeRange, setTimeRange] = useState('12m');
  const [showConfidence, setShowConfidence] = useState(true);

  // Filter data based on selected time range
  const filteredData = useMemo(() => {
    if (!data || data.length === 0) return defaultTrendData;
    
    let sliceStart = 0;
    if (timeRange === '6m') sliceStart = Math.max(0, data.length - 6);
    if (timeRange === '3m') sliceStart = Math.max(0, data.length - 3);
    
    return data.slice(sliceStart);
  }, [data, timeRange]);

  // Calculate some quick insights for the header
  const latestPrediction = filteredData[filteredData.length - 1]?.predicted || 0;
  const currentActual = filteredData.find(d => d.actual !== null && d.predicted !== null)?.actual || 0;
  const percentChange = currentActual ? (((latestPrediction - currentActual) / currentActual) * 100).toFixed(1) : 0;
  const isTrendingUp = percentChange > 0;

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      {/* Header Section */}
      <div className="p-6 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-5 h-5 text-primary" />
            <h3 className="font-display text-lg font-semibold text-foreground">AI Predictive Trend Analysis</h3>
          </div>
          <p className="text-sm text-muted-foreground font-body flex items-center gap-1">
            <Info className="w-4 h-4" />
            Forecasting corruption report volumes based on historical patterns and seasonal anomalies.
          </p>
        </div>
        
        <div className="flex items-center gap-2 self-start sm:self-auto bg-secondary/50 p-1 rounded-lg border border-border">
          {['3m', '6m', '12m'].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                timeRange === range 
                  ? 'bg-background text-foreground shadow-sm border border-border' 
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
              }`}
            >
              {range.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Insights Banner */}
      <div className="px-6 py-3 bg-secondary/30 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-full ${isTrendingUp ? 'bg-accent/10 text-accent' : 'bg-primary/10 text-primary'}`}>
            <AlertCircle className="w-4 h-4" />
          </div>
          <span className="text-sm font-body text-foreground">
            Model predicts a <strong className={isTrendingUp ? 'text-accent' : 'text-primary'}>{Math.abs(percentChange)}% {isTrendingUp ? 'increase' : 'decrease'}</strong> in report volume by end of period.
          </span>
        </div>
        
        <label className="flex items-center gap-2 cursor-pointer">
          <input 
            type="checkbox" 
            checked={showConfidence}
            onChange={(e) => setShowConfidence(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary bg-background"
          />
          <span className="text-xs font-medium text-muted-foreground">Show Confidence Interval</span>
        </label>
      </div>

      {/* Chart Area */}
      <div className="p-6 flex-grow min-h-[350px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={filteredData}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-border opacity-50" vertical={false} />
            <XAxis 
              dataKey="month" 
              stroke="currentColor" 
              className="text-muted-foreground text-xs font-body"
              tickLine={false}
              axisLine={false}
              dy={10}
            />
            <YAxis 
              stroke="currentColor" 
              className="text-muted-foreground text-xs font-body"
              tickLine={false}
              axisLine={false}
              dx={-10}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend 
              verticalAlign="top" 
              height={36}
              iconType="circle"
              wrapperStyle={{ fontSize: '12px', fontFamily: 'Inter, sans-serif', color: 'var(--text-muted-foreground)' }}
            />
            
            {/* Historical Data Line */}
            <Line 
              type="monotone" 
              dataKey="actual" 
              name="Historical Data"
              stroke="#059669" // Primary color
              strokeWidth={3}
              dot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
              activeDot={{ r: 6, strokeWidth: 0, fill: '#059669' }}
              connectNulls
            />
            
            {/* AI Prediction Line */}
            <Line 
              type="monotone" 
              dataKey="predicted" 
              name="AI Forecast"
              stroke="#D97706" // Accent color
              strokeWidth={3}
              strokeDasharray="5 5"
              dot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
              activeDot={{ r: 6, strokeWidth: 0, fill: '#D97706' }}
              connectNulls
            />

            {/* Confidence Intervals */}
            {showConfidence && (
              <>
                <Line 
                  type="monotone" 
                  dataKey="upperBound" 
                  name="Upper Bound"
                  stroke="#D97706"
                  strokeWidth={1}
                  strokeOpacity={0.3}
                  dot={false}
                  activeDot={false}
                  connectNulls
                />
                <Line 
                  type="monotone" 
                  dataKey="lowerBound" 
                  name="Lower Bound"
                  stroke="#D97706"
                  strokeWidth={1}
                  strokeOpacity={0.3}
                  dot={false}
                  activeDot={false}
                  connectNulls
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}