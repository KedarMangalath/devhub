"use client";

import { useState } from 'react';
import axios from 'axios';
import { Bot, AlertCircle, Activity, ArrowRight } from 'lucide-react';

interface AIResponse {
  analysis: string;
  urgency: string;
  recommendedDepartment: string;
}

export default function AISymptomChecker() {
  const [symptoms, setSymptoms] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIResponse | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symptoms.trim()) return;

    setLoading(true);
    try {
      const res = await axios.post('http://localhost:3001/api/ai/symptom-check', { symptoms });
      setResult(res.data);
    } catch (error) {
      console.error('AI analysis failed', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-omnia-100 text-omnia-600 mb-2">
          <Bot className="w-8 h-8" />
        </div>
        <h1 className="text-3xl font-bold text-slate-800">AI Symptom Checker</h1>
        <p className="text-slate-500 max-w-2xl mx-auto">
          Describe how you are feeling in your own words. Our AI will analyze your symptoms and recommend the best course of action or specialist to see.
        </p>
      </div>

      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <form onSubmit={handleAnalyze} className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            What are your symptoms?
          </label>
          <textarea
            rows={4}
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
            placeholder="E.g., I have had a severe headache for the past two days, along with sensitivity to light..."
            className="w-full border border-slate-300 rounded-xl p-4 focus:outline-none focus:ring-2 focus:ring-omnia-500 resize-none"
            required
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading || !symptoms.trim()}
              className="flex items-center px-6 py-3 bg-slate-900 text-white rounded-xl font-medium hover:bg-slate-800 transition-colors disabled:opacity-50"
            >
              {loading ? 'Analyzing...' : 'Analyze Symptoms'}
              {!loading && <ArrowRight className="w-4 h-4 ml-2" />}
            </button>
          </div>
        </form>
      </div>

      {result && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex items-center space-x-2">
            <Activity className="w-5 h-5 text-omnia-600" />
            <h2 className="text-lg font-semibold text-slate-800">Analysis Results</h2>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <h3 className="text-sm font-medium text-slate-500 mb-2">AI Assessment</h3>
              <p className="text-slate-800 leading-relaxed">{result.analysis}</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl border border-slate-100 bg-slate-50">
                <div className="flex items-center space-x-2 mb-1">
                  <AlertCircle className={`w-4 h-4 ${result.urgency === 'High' ? 'text-red-500' : 'text-blue-500'}`} />
                  <span className="text-sm font-medium text-slate-500">Urgency Level</span>
                </div>
                <p className={`font-bold ${result.urgency === 'High' ? 'text-red-600' : 'text-slate-800'}`}>
                  {result.urgency || 'Standard'}
                </p>
              </div>
              <div className="p-4 rounded-xl border border-slate-100 bg-slate-50">
                <div className="flex items-center space-x-2 mb-1">
                  <Bot className="w-4 h-4 text-omnia-500" />
                  <span className="text-sm font-medium text-slate-500">Recommended Specialist</span>
                </div>
                <p className="font-bold text-slate-800">
                  {result.recommendedDepartment}
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <p className="text-xs text-slate-400 text-center">
                Disclaimer: This AI tool is for informational purposes only and does not replace professional medical advice, diagnosis, or treatment.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
