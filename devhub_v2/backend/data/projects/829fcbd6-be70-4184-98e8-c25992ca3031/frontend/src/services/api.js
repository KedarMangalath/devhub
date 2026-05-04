const API_URL = 'http://localhost:3001/api';

export const submitComplaint = async (data) => {
  const res = await fetch(`${API_URL}/complaints`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to submit');
  return res.json();
};

export const trackComplaint = async (trackingId) => {
  const res = await fetch(`${API_URL}/complaints/track/${trackingId}`);
  if (!res.ok) throw new Error('Complaint not found');
  return res.json();
};

export const getComplaints = async () => {
  const res = await fetch(`${API_URL}/complaints`);
  if (!res.ok) throw new Error('Failed to fetch');
  return res.json();
};

export const updateComplaintStatus = async (id, status) => {
  const res = await fetch(`${API_URL}/complaints/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });
  if (!res.ok) throw new Error('Failed to update');
  return res.json();
};

export const getAnalytics = async () => {
  const res = await fetch(`${API_URL}/analytics/summary`);
  if (!res.ok) throw new Error('Failed to fetch analytics');
  return res.json();
};