const generateHash = () => '0x' + Array.from({length: 40}, () => Math.floor(Math.random()*16).toString(16)).join('');

export const initialComplaints = [
  {
    id: 'C3MS-8492',
    date: '2025-05-28',
    department: 'Revenue',
    location: 'Thiruvananthapuram Taluk Office',
    category: 'Bribery',
    description: 'Village officer demanded INR 5000 for issuing a possession certificate for my ancestral property. I have audio recording of the conversation.',
    status: 'Under Review',
    severity: 'High',
    aiScore: 92,
    aiSummary: 'Complainant alleges a demand of INR 5000 by a Village Officer in Thiruvananthapuram for a possession certificate. Audio evidence is claimed to be available.',
    complainant: { name: 'Rahul M.', phone: '98765XXXXX', isAnonymous: false },
    evidence: ['https://picsum.photos/seed/ev1/400/300'],
    blockchainHash: generateHash(),
    timeline: [
      { date: '2025-05-28 10:15 AM', action: 'Complaint Submitted via Web Portal', actor: 'Citizen', hash: generateHash() },
      { date: '2025-05-28 10:16 AM', action: 'AI Categorization & Scoring Completed', actor: 'System', hash: generateHash() },
      { date: '2025-05-29 09:00 AM', action: 'Assigned to Inspector Rajesh K.', actor: 'System', hash: generateHash() }
    ]
  },
  {
    id: 'C3MS-8493',
    date: '2025-05-29',
    department: 'PWD',
    location: 'Kochi Corporation',
    category: 'Contractor Fraud',
    description: 'Road tarring work in Ward 12 was completed yesterday but it is already washing away in the rain. The contractor used substandard materials in collusion with the assistant engineer.',
    status: 'Investigation In Progress',
    severity: 'Critical',
    aiScore: 88,
    aiSummary: 'Allegation of substandard road construction materials used in Ward 12, Kochi, implying collusion between contractor and PWD Assistant Engineer.',
    complainant: { name: 'Anonymous', phone: 'Hidden', isAnonymous: true },
    evidence: ['https://picsum.photos/seed/ev2/400/300', 'https://picsum.photos/seed/ev3/400/300'],
    blockchainHash: generateHash(),
    timeline: [
      { date: '2025-05-29 14:20 PM', action: 'Complaint Submitted via Mobile App', actor: 'Citizen', hash: generateHash() },
      { date: '2025-05-30 11:00 AM', action: 'Field Visit Scheduled', actor: 'Inspector Anitha', hash: generateHash() }
    ]
  },
  {
    id: 'C3MS-8494',
    date: '2025-06-01',
    department: 'Police',
    location: 'Kollam East PS',
    category: 'Service Denial',
    description: 'Station House Officer refused to register an FIR for a stolen vehicle and asked me to settle it privately.',
    status: 'Submitted',
    severity: 'Medium',
    aiScore: 75,
    aiSummary: 'Complainant states SHO at Kollam East PS refused to file an FIR for a stolen vehicle, suggesting private settlement.',
    complainant: { name: 'Suresh Kumar', phone: '94471XXXXX', isAnonymous: false },
    evidence: [],
    blockchainHash: generateHash(),
    timeline: [
      { date: '2025-06-01 08:45 AM', action: 'Complaint Submitted via WhatsApp', actor: 'Citizen', hash: generateHash() }
    ]
  },
  {
    id: 'C3MS-8495',
    date: '2025-05-15',
    department: 'LSGD',
    location: 'Palakkad Municipality',
    category: 'Favoritism',
    description: 'Building permit granted to a commercial complex violating wetland rules. The beneficiary is a close relative of the municipal secretary.',
    status: 'Escalated',
    severity: 'High',
    aiScore: 95,
    aiSummary: 'Alleged illegal building permit issuance in Palakkad violating wetland regulations due to nepotism involving the Municipal Secretary.',
    complainant: { name: 'Environmental Watch NGO', phone: '04842XXXXX', isAnonymous: false },
    evidence: ['https://picsum.photos/seed/ev4/400/300'],
    blockchainHash: generateHash(),
    timeline: [
      { date: '2025-05-15 11:00 AM', action: 'Complaint Submitted via Email', actor: 'Citizen', hash: generateHash() },
      { date: '2025-05-30 11:00 AM', action: 'Auto-Escalated (15 days SLA breached)', actor: 'System', hash: generateHash() }
    ]
  },
  {
    id: 'C3MS-8496',
    date: '2025-05-10',
    department: 'Health',
    location: 'Govt Medical College, Kozhikode',
    category: 'Misappropriation',
    description: 'Medicines meant for free distribution are being diverted to private pharmacies by store keepers.',
    status: 'Resolved',
    severity: 'Critical',
    aiScore: 89,
    aiSummary: 'Report of free government medicines being illegally diverted to private pharmacies by store staff at Kozhikode Medical College.',
    complainant: { name: 'Anonymous', phone: 'Hidden', isAnonymous: true },
    evidence: [],
    blockchainHash: generateHash(),
    timeline: [
      { date: '2025-05-10 09:00 AM', action: 'Complaint Submitted via IVR', actor: 'Citizen', hash: generateHash() },
      { date: '2025-05-25 16:30 PM', action: 'Investigation Concluded. 2 Suspended.', actor: 'DySP Thomas', hash: generateHash() },
      { date: '2025-05-26 10:00 AM', action: 'Marked as Resolved', actor: 'DySP Thomas', hash: generateHash() }
    ]
  },
  // Adding more to meet the 15+ requirement
  ...Array.from({length: 12}).map((_, i) => ({
    id: `C3MS-${8497 + i}`,
    date: new Date(Date.now() - Math.random() * 10000000000).toISOString().split('T')[0],
    department: ['Revenue', 'PWD', 'Police', 'LSGD', 'Health', 'Education', 'Motor Vehicles'][Math.floor(Math.random() * 7)],
    location: `District Office ${Math.floor(Math.random() * 14) + 1}`,
    category: ['Bribery', 'Service Denial', 'Favoritism', 'Misappropriation', 'Document Forgery', 'Land Encroachment'][Math.floor(Math.random() * 6)],
    description: 'Standard generated complaint description for testing the dashboard density and scrolling capabilities.',
    status: ['Submitted', 'Under Review', 'Investigation In Progress', 'Resolved', 'Closed'][Math.floor(Math.random() * 5)],
    severity: ['Low', 'Medium', 'High', 'Critical'][Math.floor(Math.random() * 4)],
    aiScore: Math.floor(Math.random() * 40) + 50,
    aiSummary: 'Auto-generated summary by NLP engine.',
    complainant: { name: 'Citizen', phone: 'Hidden', isAnonymous: true },
    evidence: [],
    blockchainHash: generateHash(),
    timeline: [{ date: '2025-06-01 10:00 AM', action: 'Intake Logged', actor: 'System', hash: generateHash() }]
  }))
];

export const analyticsData = {
  departmentStats: [
    { name: 'Revenue', complaints: 145 },
    { name: 'LSGD', complaints: 112 },
    { name: 'Police', complaints: 89 },
    { name: 'PWD', complaints: 76 },
    { name: 'Health', complaints: 45 },
    { name: 'MVD', complaints: 34 }
  ],
  severityStats: [
    { name: 'Critical', value: 15, fill: '#ef4444' },
    { name: 'High', value: 45, fill: '#f97316' },
    { name: 'Medium', value: 120, fill: '#eab308' },
    { name: 'Low', value: 60, fill: '#3b82f6' }
  ],
  monthlyTrends: [
    { month: 'Jan', count: 65 },
    { month: 'Feb', count: 78 },
    { month: 'Mar', count: 90 },
    { month: 'Apr', count: 115 },
    { month: 'May', count: 140 },
    { month: 'Jun', count: 185 }
  ]
};