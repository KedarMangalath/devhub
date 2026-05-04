import { initialComplaints, analyticsData } from '../mockData';

// In-memory store to simulate backend persistence during session
let complaintsStore = [...initialComplaints];

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const generateHash = () => '0x' + Array.from({length: 40}, () => Math.floor(Math.random()*16).toString(16)).join('');

export const api = {
  getComplaints: async () => {
    await delay(400);
    return [...complaintsStore].sort((a, b) => new Date(b.date) - new Date(a.date));
  },
  
  getComplaintById: async (id) => {
    await delay(300);
    return complaintsStore.find(c => c.id === id);
  },
  
  submitComplaint: async (data) => {
    await delay(800); // Simulate AI processing time
    
    const newId = `C3MS-${Math.floor(9000 + Math.random() * 1000)}`;
    const now = new Date();
    
    const newComplaint = {
      id: newId,
      date: now.toISOString().split('T')[0],
      department: data.department,
      location: data.location,
      category: data.category || 'Uncategorized',
      description: data.description,
      status: 'Submitted',
      severity: ['Medium', 'High', 'Critical'][Math.floor(Math.random() * 3)], // Simulated AI severity
      aiScore: Math.floor(70 + Math.random() * 25), // Simulated AI credibility
      aiSummary: `AI Summary: Complainant reports an issue regarding ${data.category} at ${data.location} involving ${data.department}.`,
      complainant: {
        name: data.isAnonymous ? 'Anonymous' : data.name,
        phone: data.isAnonymous ? 'Hidden' : data.phone,
        isAnonymous: data.isAnonymous
      },
      evidence: data.hasEvidence ? ['https://picsum.photos/seed/new/400/300'] : [],
      blockchainHash: generateHash(),
      timeline: [
        { 
          date: now.toLocaleString(), 
          action: `Complaint Submitted via ${data.channel || 'Web Portal'}`, 
          actor: 'Citizen', 
          hash: generateHash() 
        },
        { 
          date: new Date(now.getTime() + 2000).toLocaleString(), 
          action: 'AI Categorization & Scoring Completed', 
          actor: 'System', 
          hash: generateHash() 
        }
      ]
    };
    
    complaintsStore.unshift(newComplaint);
    return { success: true, id: newId };
  },
  
  updateComplaintStatus: async (id, newStatus, note) => {
    await delay(500);
    const index = complaintsStore.findIndex(c => c.id === id);
    if (index !== -1) {
      complaintsStore[index] = {
        ...complaintsStore[index],
        status: newStatus,
        timeline: [
          ...complaintsStore[index].timeline,
          { 
            date: new Date().toLocaleString(), 
            action: `Status updated to ${newStatus}${note ? ': ' + note : ''}`, 
            actor: 'Officer', 
            hash: generateHash() 
          }
        ]
      };
      return { success: true, complaint: complaintsStore[index] };
    }
    throw new Error('Complaint not found');
  },

  getAnalytics: async () => {
    await delay(300);
    return analyticsData;
  }
};