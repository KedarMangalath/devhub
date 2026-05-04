import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { Map, AlertTriangle, TrendingUp, Users } from 'lucide-react';

export default function AnalyticsDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      const result = await api.getAnalytics();
      setData(result);
    };
    fetchData();
  }, []);

  if (!data) return <div className="py-12 text-center">Loading analytics engine...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Executive Analytics Dashboard</h1>
        <p className="text-gray-500 text-sm">Director-level strategic view of corruption trends and system KPIs.</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-5 flex items-center">
          <div className="bg-blue-100 p-3 rounded-lg mr-4">
            <TrendingUp className="h-6 w-6 text-blue-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Total Complaints (YTD)</p>
            <p className="text-2xl font-bold text-gray-900">673</p>
            <p className="text-xs text-green-600">+12% vs last month</p>
          </div>
        </div>
        <div className="card p-5 flex items-center">
          <div className="bg-green-100 p-3 rounded-lg mr-4">
            <Map className="h-6 w-6 text-green-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Avg Resolution Time</p>
            <p className="text-2xl font-bold text-gray-900">18 Days</p>
            <p className="text-xs text-green-600">Target: 30 Days</p>
          </div>
        </div>
        <div className="card p-5 flex items-center">
          <div className="bg-purple-100 p-3 rounded-lg mr-4">
            <Users className="h-6 w-6 text-purple-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Anonymous Ratio</p>
            <p className="text-2xl font-bold text-gray-900">42%</p>
            <p className="text-xs text-gray-500">Indicating high system trust</p>
          </div>
        </div>
        <div className="card p-5 flex items-center">
          <div className="bg-red-100 p-3 rounded-lg mr-4">
            <AlertTriangle className="h-6 w-6 text-red-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">AI Predicted Hotspots</p>
            <p className="text-2xl font-bold text-gray-900">3</p>
            <p className="text-xs text-red-600">Requires immediate review</p>
          </div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">Complaints by Department</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.departmentStats} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" />
                <YAxis dataKey="name" type="category" width={80} />
                <Tooltip cursor={{fill: '#f3f4f6'}} />
                <Bar dataKey="complaints" fill="#0f766e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">Severity Distribution</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.severityStats}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {data.severityStats.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold mb-4">Intake Volume Trend (6 Months)</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.monthlyTrends} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}