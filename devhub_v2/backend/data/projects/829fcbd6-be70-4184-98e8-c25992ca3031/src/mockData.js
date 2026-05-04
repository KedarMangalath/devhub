export const categories = [
  { id: 'cat-1', name: 'Public Works (PWD)', count: 142, icon: 'HardHat', color: '#D97706' },
  { id: 'cat-2', name: 'Revenue Department', count: 315, icon: 'FileText', color: '#059669' },
  { id: 'cat-3', name: 'Local Self Govt (LSGD)', count: 284, icon: 'Building', color: '#2563EB' },
  { id: 'cat-4', name: 'Motor Vehicles (MVD)', count: 198, icon: 'Car', color: '#DC2626' },
  { id: 'cat-5', name: 'Health Services', count: 156, icon: 'Activity', color: '#0D9488' },
  { id: 'cat-6', name: 'Kerala Police', count: 210, icon: 'Shield', color: '#4F46E5' },
  { id: 'cat-7', name: 'Civil Supplies', count: 89, icon: 'ShoppingCart', color: '#EA580C' },
  { id: 'cat-8', name: 'Education Dept', count: 112, icon: 'BookOpen', color: '#7C3AED' },
  { id: 'cat-9', name: 'Forest Department', count: 67, icon: 'TreePine', color: '#16A34A' },
  { id: 'cat-10', name: 'Excise Department', count: 94, icon: 'Wine', color: '#BE123C' }
];

export const dashboardMetrics = [
  { id: 'm-1', label: 'Total Complaints', value: '12,450', trend: '+14%', detail: 'vs last month', icon: 'FileText' },
  { id: 'm-2', label: 'Resolved Cases', value: '8,234', trend: '+22%', detail: 'vs last month', icon: 'CheckCircle' },
  { id: 'm-3', label: 'Active Investigations', value: '3,102', trend: '-5%', detail: 'vs last month', icon: 'Search' },
  { id: 'm-4', label: 'Funds Recovered', value: '₹12.4Cr', trend: '+45%', detail: 'YTD recovery', icon: 'IndianRupee' },
  { id: 'm-5', label: 'Avg Resolution Time', value: '30 Days', trend: '-12%', detail: 'Faster than avg', icon: 'Clock' },
  { id: 'm-6', label: 'AI Credibility Flags', value: '1,420', trend: '+8%', detail: 'High risk alerts', icon: 'AlertTriangle' },
  { id: 'm-7', label: 'Anonymous Reports', value: '68%', trend: '+2%', detail: 'Of total volume', icon: 'UserX' },
  { id: 'm-8', label: 'System Uptime', value: '99.9%', trend: '0%', detail: 'Last 90 days', icon: 'Server' }
];

export const userProfile = {
  id: 'usr-991',
  name: 'Dr. Rajesh Kumar',
  email: 'rajesh.kumar@vigilance.kerala.gov.in',
  role: 'Chief Investigating Officer',
  avatar: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=800&q=80',
  preferences: {
    notifications: true,
    darkMode: false,
    language: 'en',
    twoFactorEnabled: true
  },
  stats: {
    casesAssigned: 45,
    casesResolved: 312,
    successRate: '94%',
    activeAlerts: 3
  },
  department: 'Anti-Corruption Bureau',
  location: 'Thiruvananthapuram HQ'
};

export const messages = [
  { id: 'msg-1', sender: 'System AI', preview: 'High risk anomaly detected in PWD contract #4421.', timestamp: '2023-10-24T09:00:00Z', unread: true },
  { id: 'msg-2', sender: 'Citizen #8842', preview: 'I have uploaded the audio recording as requested.', timestamp: '2023-10-24T08:30:00Z', unread: true },
  { id: 'msg-3', sender: 'Director General', preview: 'Please review the quarterly audit report for LSGD.', timestamp: '2023-10-23T16:45:00Z', unread: false },
  { id: 'msg-4', sender: 'Legal Team', preview: 'Warrant approved for search at Revenue Office, Kochi.', timestamp: '2023-10-23T14:20:00Z', unread: false },
  { id: 'msg-5', sender: 'Citizen #9102', preview: 'Is there any update on my complaint regarding the ration shop?', timestamp: '2023-10-22T11:15:00Z', unread: false },
  { id: 'msg-6', sender: 'System AI', preview: 'Blockchain verification complete for Evidence Batch A.', timestamp: '2023-10-22T09:05:00Z', unread: false },
  { id: 'msg-7', sender: 'Inspector Priya', preview: 'I will take over the MVD bribery case from tomorrow.', timestamp: '2023-10-21T18:30:00Z', unread: false },
  { id: 'msg-8', sender: 'Citizen #7731', preview: 'Thank you, the officer has been transferred.', timestamp: '2023-10-20T10:00:00Z', unread: false },
  { id: 'msg-9', sender: 'IT Support', preview: 'Scheduled maintenance for the secure upload portal tonight.', timestamp: '2023-10-19T15:45:00Z', unread: false },
  { id: 'msg-10', sender: 'System AI', preview: 'Duplicate complaint detected. Merging with Case #1092.', timestamp: '2023-10-18T08:20:00Z', unread: false }
];

export const testimonials = [
  { id: 't-1', quote: "I was afraid to report the bribe requested for my land registration. The anonymous WhatsApp bot made it safe and easy. The officer was suspended within weeks.", name: "Anonymous Citizen", role: "Small Business Owner", company: "Kochi", avatar: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=800&q=80", rating: 5 },
  { id: 't-2', quote: "The blockchain tracking gave me confidence that my complaint couldn't be deleted or altered by powerful people. True transparency.", name: "Suresh M.", role: "Activist", company: "Thrissur", avatar: "https://images.unsplash.com/photo-1599566150163-29194dcaad36?w=800&q=80", rating: 5 },
  { id: 't-3', quote: "As an investigator, the AI predictive alerts help me focus on high-risk cases before funds are completely siphoned off. It's a game changer.", name: "Priya K.", role: "Vigilance Officer", company: "Trivandrum", avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=800&q=80", rating: 5 },
  { id: 't-4', quote: "Reporting illegal sand mining used to be dangerous. Now I can drop a pin and upload photos securely without revealing my identity.", name: "Local Resident", role: "Farmer", company: "Palakkad", avatar: "https://images.unsplash.com/photo-1527980965255-d3b416303d12?w=800&q=80", rating: 4 },
  { id: 't-5', quote: "The dashboard is incredibly intuitive. We recovered ₹2.5Cr in misallocated funds just last month using the pattern recognition tools.", name: "Director General", role: "Administration", company: "State Govt", avatar: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=800&q=80", rating: 5 },
  { id: 't-6', quote: "I faced constant delays for my building permit until I used C3MS. The issue was resolved in 4 days after the AI flagged the delay as anomalous.", name: "Anita V.", role: "Homeowner", company: "Kozhikode", avatar: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=800&q=80", rating: 5 },
  { id: 't-7', quote: "Excellent initiative by the government. The interface is clean, and the status updates keep you informed every step of the way.", name: "Rahul Nair", role: "Software Engineer", company: "Technopark", avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&q=80", rating: 4 },
  { id: 't-8', quote: "The integration of Malayalam language support in the reporting tool makes it accessible to everyone in our village.", name: "Gopalan", role: "Panchayat Member", company: "Wayanad", avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=800&q=80", rating: 5 }
];

export const pricingTiers = [
  {
    id: 'tier-1',
    name: 'Citizen Access',
    price: 'Free',
    description: 'Standard access for all citizens to report and track.',
    features: ['Anonymous Reporting', 'Basic Status Tracking', 'Secure Evidence Upload', 'Multilingual Support', 'WhatsApp Bot Access']
  },
  {
    id: 'tier-2',
    name: 'Investigator Pro',
    price: 'Internal',
    description: 'Advanced tools for verified vigilance officers.',
    features: ['AI Credibility Scoring', 'Blockchain Audit Trails', 'Predictive Risk Alerts', 'Cross-Department Search', 'Encrypted Comms Channel']
  },
  {
    id: 'tier-3',
    name: 'Enterprise Gov',
    price: 'Custom',
    description: 'Full deployment for state-level administration.',
    features: ['Statewide Heatmaps', 'Custom KPI Dashboards', 'API Integrations', 'Dedicated Support', 'Advanced Data Export']
  }
];

export const faqItems = [
  { question: "Is my identity truly anonymous?", answer: "Yes. If you choose anonymous reporting, your personal details are stripped before the complaint enters the main database. We use zero-knowledge proofs to ensure even system admins cannot trace the report back to you." },
  { question: "What kind of evidence should I upload?", answer: "Audio recordings, video clips, photographs, scanned documents, or screenshots of messages are all helpful. Ensure the files clearly show the corrupt practice or demand." },
  { question: "How does the AI credibility score work?", answer: "Our AI analyzes the complaint for consistency, cross-references it with historical data, checks for duplicate patterns, and evaluates the metadata of uploaded evidence to assign a preliminary credibility score." },
  { question: "Can a powerful official delete my complaint?", answer: "No. Every submitted complaint and its evidence hash is logged on an immutable blockchain ledger. Once recorded, it cannot be altered or deleted by anyone, ensuring complete transparency." },
  { question: "How long does an investigation take?", answer: "While simple cases may be resolved in a few weeks, complex investigations involving multiple departments can take months. You can track the real-time status on your dashboard." },
  { question: "What happens if I submit a false complaint?", answer: "The system uses AI to detect malicious or coordinated false reporting. Deliberate false complaints can lead to legal action, as the system aims to protect honest officials as well." },
  { question: "Can I report issues from any district in Kerala?", answer: "Yes, the C3MS covers all 14 districts and all major state government departments." },
  { question: "Do I need a smartphone to report?", answer: "No. While the web portal and app offer the best experience, you can also report via SMS, our automated WhatsApp bot, or by calling the toll-free vigilance hotline." },
  { question: "How is recovered money handled?", answer: "Funds recovered through vigilance actions are returned to the state treasury or the rightful owner, depending on the nature of the case, following strict legal protocols." },
  { question: "Who reviews my complaint?", answer: "Initial triage is done by AI. High-credibility complaints are immediately assigned to a verified Vigilance Investigating Officer in the relevant jurisdiction." }
];

export const processSteps = [
  { id: 'step-1', title: 'Select Category', description: 'Choose the department or nature of the corruption you wish to report.', icon: 'List' },
  { id: 'step-2', title: 'Provide Details', description: 'Enter the specifics: who, what, when, and where. You can remain anonymous.', icon: 'FileText' },
  { id: 'step-3', title: 'Upload Evidence', description: 'Securely attach photos, audio, or documents. Files are encrypted instantly.', icon: 'UploadCloud' },
  { id: 'step-4', title: 'AI Credibility Check', description: 'Our system analyzes the submission to prioritize high-risk cases.', icon: 'Cpu' },
  { id: 'step-5', title: 'Secure Submission', description: 'Your report is logged on the blockchain and assigned to an investigator.', icon: 'ShieldCheck' }
];

export const primaryItems = [
  {
    id: 'cmp-001',
    title: 'Bribery Request for Building Permit',
    description: 'An official at the local panchayat office demanded ₹50,000 to clear a residential building permit that has been pending for 6 months despite all documents being in order.',
    category: 'Local Self Govt (LSGD)',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=800&q=80',
    rating: 92,
    date: '2023-10-20',
    tags: ['Bribery', 'Permit', 'Delay'],
    metadata: { location: 'Kochi', evidenceCount: 3, blockchainHash: '0x8f...3a1b', riskLevel: 'High' }
  },
  {
    id: 'cmp-002',
    title: 'Substandard Materials in Road Construction',
    description: 'The contractor for the new bypass road is using visibly inferior tar and aggregate. The road is already developing potholes within weeks of laying.',
    category: 'Public Works (PWD)',
    status: 'Resolved',
    image: 'https://images.unsplash.com/photo-1518242007635-49811d88b48f?w=800&q=80',
    rating: 88,
    date: '2023-09-15',
    tags: ['Fraud', 'Infrastructure', 'Quality'],
    metadata: { location: 'Thrissur', evidenceCount: 5, blockchainHash: '0x2c...9f4e', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-003',
    title: 'Disproportionate Assets - RTO Official',
    description: 'A Motor Vehicles Inspector has recently purchased three luxury properties and multiple vehicles, which is vastly disproportionate to their known sources of income.',
    category: 'Motor Vehicles (MVD)',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=800&q=80',
    rating: 75,
    date: '2023-10-22',
    tags: ['Assets', 'Suspicious Wealth'],
    metadata: { location: 'Thiruvananthapuram', evidenceCount: 1, blockchainHash: '0x1a...7b2c', riskLevel: 'High' }
  },
  {
    id: 'cmp-004',
    title: 'Illegal Sand Mining Collusion',
    description: 'Local police are allegedly turning a blind eye to illegal sand mining operations in the riverbed during night hours in exchange for regular payoffs.',
    category: 'Kerala Police',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1621864316024-81ceb01b611c?w=800&q=80',
    rating: 95,
    date: '2023-10-18',
    tags: ['Collusion', 'Environment', 'Mining'],
    metadata: { location: 'Palakkad', evidenceCount: 4, blockchainHash: '0x9d...4c1a', riskLevel: 'Critical' }
  },
  {
    id: 'cmp-005',
    title: 'Fake Medical Certificates Issuance',
    description: 'A doctor at the district hospital is issuing fake medical certificates for government employees to claim extended paid leave, charging ₹2000 per certificate.',
    category: 'Health Services',
    status: 'Resolved',
    image: 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=800&q=80',
    rating: 82,
    date: '2023-08-10',
    tags: ['Forgery', 'Medical', 'Bribe'],
    metadata: { location: 'Kollam', evidenceCount: 2, blockchainHash: '0x4e...1f8d', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-006',
    title: 'Ration Shop Grain Diversion',
    description: 'The licensee of ration shop #442 is diverting subsidized rice and wheat to the open market while telling cardholders that stock has not arrived.',
    category: 'Civil Supplies',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1587478640470-89d66ff23bf2?w=800&q=80',
    rating: 89,
    date: '2023-10-12',
    tags: ['Theft', 'Subsidies', 'Food'],
    metadata: { location: 'Alappuzha', evidenceCount: 6, blockchainHash: '0x7b...3e9a', riskLevel: 'High' }
  },
  {
    id: 'cmp-007',
    title: 'Extortion for Land Mutation',
    description: 'Village officer is refusing to process the Pokkuvaravu (mutation) of my inherited land unless I pay a "processing fee" of ₹15,000 directly to his personal aide.',
    category: 'Revenue Department',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800&q=80',
    rating: 91,
    date: '2023-10-23',
    tags: ['Extortion', 'Land', 'Revenue'],
    metadata: { location: 'Kottayam', evidenceCount: 2, blockchainHash: '0x5c...8a2f', riskLevel: 'High' }
  },
  {
    id: 'cmp-008',
    title: 'School Fund Misappropriation',
    description: 'The headmaster of the Govt UP School has allegedly created fake bills for infrastructure repairs that were never carried out, siphoning off PTA and Govt funds.',
    category: 'Education Dept',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1580582932707-520aed937b7b?w=800&q=80',
    rating: 78,
    date: '2023-09-28',
    tags: ['Embezzlement', 'Education', 'Funds'],
    metadata: { location: 'Malappuram', evidenceCount: 3, blockchainHash: '0x3f...6d1b', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-009',
    title: 'Illegal Tree Felling in Reserve',
    description: 'Teak trees are being illegally cut and transported from the reserve forest area with the alleged knowledge of the local forest beat officer.',
    category: 'Forest Department',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1448375240586-882707db888b?w=800&q=80',
    rating: 85,
    date: '2023-10-21',
    tags: ['Smuggling', 'Environment', 'Forest'],
    metadata: { location: 'Wayanad', evidenceCount: 4, blockchainHash: '0x8a...2c5e', riskLevel: 'Critical' }
  },
  {
    id: 'cmp-010',
    title: 'Bar License Renewal Bribe',
    description: 'Excise officials are demanding a massive payoff to renew the annual license for a local bar, threatening to file false violation reports if not paid.',
    category: 'Excise Department',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=800&q=80',
    rating: 94,
    date: '2023-10-15',
    tags: ['Bribery', 'License', 'Excise'],
    metadata: { location: 'Ernakulam', evidenceCount: 2, blockchainHash: '0x1e...9b4d', riskLevel: 'High' }
  },
  {
    id: 'cmp-011',
    title: 'Ghost Workers in MGNREGA',
    description: 'Panchayat members are listing deceased individuals and non-residents on the MGNREGA muster rolls and pocketing their daily wages.',
    category: 'Local Self Govt (LSGD)',
    status: 'Resolved',
    image: 'https://images.unsplash.com/photo-1584291527908-033f4d6542c8?w=800&q=80',
    rating: 88,
    date: '2023-07-12',
    tags: ['Fraud', 'Wages', 'Rural'],
    metadata: { location: 'Idukki', evidenceCount: 8, blockchainHash: '0x6d...3f2a', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-012',
    title: 'Overpricing of Hospital Supplies',
    description: 'The procurement officer at the General Hospital is buying surgical gloves and masks at 300% of the market rate from a shell company owned by a relative.',
    category: 'Health Services',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800&q=80',
    rating: 96,
    date: '2023-10-05',
    tags: ['Procurement', 'Nepotism', 'Medical'],
    metadata: { location: 'Thiruvananthapuram', evidenceCount: 5, blockchainHash: '0x2b...8e1c', riskLevel: 'Critical' }
  },
  {
    id: 'cmp-013',
    title: 'Driving Test Pass Guarantee',
    description: 'Driving school instructors are openly collecting ₹3000 extra per candidate, claiming it is a mandatory cut for the MVI to ensure they pass the driving test.',
    category: 'Motor Vehicles (MVD)',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1449965408869-eaa3f722e40d?w=800&q=80',
    rating: 81,
    date: '2023-10-24',
    tags: ['Bribery', 'Testing', 'MVD'],
    metadata: { location: 'Kozhikode', evidenceCount: 1, blockchainHash: '0x9c...4a5b', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-014',
    title: 'Police Clearance Certificate Delay',
    description: 'Station House Officer is deliberately delaying the issuance of a Police Clearance Certificate required for a visa, hinting at a "donation" to the station fund.',
    category: 'Kerala Police',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=800&q=80',
    rating: 79,
    date: '2023-10-19',
    tags: ['Delay', 'Extortion', 'Clearance'],
    metadata: { location: 'Kannur', evidenceCount: 2, blockchainHash: '0x4f...1d8e', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-015',
    title: 'Encroachment of Puramboke Land',
    description: 'A private resort is encroaching on government puramboke (unassessed) land near the backwaters. Revenue officials have ignored multiple complaints.',
    category: 'Revenue Department',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1595815431059-a9eb500d6b19?w=800&q=80',
    rating: 87,
    date: '2023-10-14',
    tags: ['Encroachment', 'Land', 'Collusion'],
    metadata: { location: 'Alappuzha', evidenceCount: 4, blockchainHash: '0x7a...2b3c', riskLevel: 'High' }
  },
  {
    id: 'cmp-016',
    title: 'Bridge Construction Kickbacks',
    description: 'Audio recording suggests a 15% kickback was agreed upon between the chief engineer and the contractor for the new river bridge project.',
    category: 'Public Works (PWD)',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=800&q=80',
    rating: 98,
    date: '2023-09-02',
    tags: ['Kickbacks', 'Infrastructure', 'Audio'],
    metadata: { location: 'Pathanamthitta', evidenceCount: 1, blockchainHash: '0x3e...9c4d', riskLevel: 'Critical' }
  },
  {
    id: 'cmp-017',
    title: 'Midday Meal Scheme Fraud',
    description: 'The quantity of provisions supplied for the school midday meal scheme is consistently 20% less than what is billed by the supplier.',
    category: 'Education Dept',
    status: 'Resolved',
    image: 'https://images.unsplash.com/photo-1509062522246-3755977927d7?w=800&q=80',
    rating: 84,
    date: '2023-06-15',
    tags: ['Fraud', 'Food', 'Children'],
    metadata: { location: 'Kasaragod', evidenceCount: 3, blockchainHash: '0x8b...1a2f', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-018',
    title: 'Smuggling of Seized Liquor',
    description: 'Liquor bottles seized during raids are allegedly being resold in the black market by lower-ranking excise officers instead of being destroyed.',
    category: 'Excise Department',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1569529465841-dfecdab7503b?w=800&q=80',
    rating: 91,
    date: '2023-10-08',
    tags: ['Smuggling', 'Contraband', 'Theft'],
    metadata: { location: 'Ernakulam', evidenceCount: 2, blockchainHash: '0x5d...4e1b', riskLevel: 'High' }
  },
  {
    id: 'cmp-019',
    title: 'Falsified Quarry Permits',
    description: 'A granite quarry is operating beyond its permitted area. The local geologist has allegedly falsified the survey reports to protect the quarry owner.',
    category: 'Revenue Department',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1516937941344-00b4e0337589?w=800&q=80',
    rating: 86,
    date: '2023-10-20',
    tags: ['Mining', 'Forgery', 'Environment'],
    metadata: { location: 'Thrissur', evidenceCount: 5, blockchainHash: '0x2f...7c3a', riskLevel: 'High' }
  },
  {
    id: 'cmp-020',
    title: 'Bribe for Trade License',
    description: 'Health inspector demanded ₹10,000 to issue a sanitary certificate required for opening a new restaurant, threatening to fail the inspection otherwise.',
    category: 'Local Self Govt (LSGD)',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&q=80',
    rating: 93,
    date: '2023-10-16',
    tags: ['Bribery', 'License', 'Business'],
    metadata: { location: 'Kochi', evidenceCount: 2, blockchainHash: '0x9e...1b4c', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-021',
    title: 'Nepotism in Temporary Appointments',
    description: 'Five temporary data entry operators hired at the district collectorate are close relatives of senior clerks, bypassing the employment exchange list.',
    category: 'Revenue Department',
    status: 'Resolved',
    image: 'https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=800&q=80',
    rating: 80,
    date: '2023-05-22',
    tags: ['Nepotism', 'Hiring', 'Favoritism'],
    metadata: { location: 'Kollam', evidenceCount: 4, blockchainHash: '0x4a...8d2e', riskLevel: 'Low' }
  },
  {
    id: 'cmp-022',
    title: 'Misuse of Official Vehicles',
    description: 'A senior police officer is regularly using the official department vehicle and driver for personal family trips outside the district.',
    category: 'Kerala Police',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1566315353163-01772186c221?w=800&q=80',
    rating: 72,
    date: '2023-10-23',
    tags: ['Misuse', 'Resources', 'Vehicles'],
    metadata: { location: 'Thiruvananthapuram', evidenceCount: 1, blockchainHash: '0x7c...3f1a', riskLevel: 'Low' }
  },
  {
    id: 'cmp-023',
    title: 'Adulterated Fuel at Civil Supplies Pump',
    description: 'The petrol pump operated by Civil Supplies is allegedly mixing solvents with petrol. Multiple vehicles have reported engine damage after refueling there.',
    category: 'Civil Supplies',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1527018601619-a508a2be00cd?w=800&q=80',
    rating: 89,
    date: '2023-10-11',
    tags: ['Adulteration', 'Fuel', 'Fraud'],
    metadata: { location: 'Kozhikode', evidenceCount: 7, blockchainHash: '0x1b...9e4d', riskLevel: 'High' }
  },
  {
    id: 'cmp-024',
    title: 'Wildlife Poaching Cover-up',
    description: 'Evidence of wild boar poaching was found in the reserve, but the local forest guards allegedly accepted a bribe to not register a case against the perpetrators.',
    category: 'Forest Department',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1475809913362-28a064ce4731?w=800&q=80',
    rating: 83,
    date: '2023-10-19',
    tags: ['Poaching', 'Cover-up', 'Wildlife'],
    metadata: { location: 'Idukki', evidenceCount: 2, blockchainHash: '0x6e...2a5c', riskLevel: 'High' }
  },
  {
    id: 'cmp-025',
    title: 'Delay in Pension Disbursement',
    description: 'Clerks at the treasury are demanding a "speed money" cut to process the arrears of retired government employees.',
    category: 'Revenue Department',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=800&q=80',
    rating: 90,
    date: '2023-10-07',
    tags: ['Bribery', 'Pension', 'Delay'],
    metadata: { location: 'Palakkad', evidenceCount: 3, blockchainHash: '0x3a...8c1f', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-026',
    title: 'Tax Evasion Collusion',
    description: 'Commercial tax officers are allegedly colluding with a major jewelry chain to underreport sales during the festival season, causing massive loss to the exchequer.',
    category: 'Revenue Department',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1554224154-26032ffc0d07?w=800&q=80',
    rating: 97,
    date: '2023-09-30',
    tags: ['Tax Evasion', 'Collusion', 'Corporate'],
    metadata: { location: 'Ernakulam', evidenceCount: 6, blockchainHash: '0x8d...4b2e', riskLevel: 'Critical' }
  },
  {
    id: 'cmp-027',
    title: 'Substandard Medicines in PHC',
    description: 'The Primary Health Centre is distributing medicines that are past their expiry date, with new labels pasted over the old ones.',
    category: 'Health Services',
    status: 'Resolved',
    image: 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800&q=80',
    rating: 95,
    date: '2023-04-12',
    tags: ['Health Hazard', 'Fraud', 'Medicines'],
    metadata: { location: 'Wayanad', evidenceCount: 4, blockchainHash: '0x2e...9a1c', riskLevel: 'Critical' }
  },
  {
    id: 'cmp-028',
    title: 'Illegal Route Permits for Private Buses',
    description: 'MVD officials are granting lucrative route permits to a specific private bus syndicate while rejecting applications from competitors on flimsy grounds.',
    category: 'Motor Vehicles (MVD)',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=800&q=80',
    rating: 84,
    date: '2023-10-22',
    tags: ['Favoritism', 'Transport', 'Permits'],
    metadata: { location: 'Kannur', evidenceCount: 2, blockchainHash: '0x9b...3c4d', riskLevel: 'Medium' }
  },
  {
    id: 'cmp-029',
    title: 'Water Authority Pipe Laying Scam',
    description: 'Contractors are billing for laying 10-inch pipes but are actually installing cheaper 8-inch pipes underground. The inspecting engineer has signed off on the work.',
    category: 'Public Works (PWD)',
    status: 'Investigating',
    image: 'https://images.unsplash.com/photo-1585704032915-c3400ca199e7?w=800&q=80',
    rating: 92,
    date: '2023-10-01',
    tags: ['Fraud', 'Infrastructure', 'Water'],
    metadata: { location: 'Thiruvananthapuram', evidenceCount: 3, blockchainHash: '0x4c...1e8a', riskLevel: 'High' }
  },
  {
    id: 'cmp-030',
    title: 'Bribe for SC/ST Certificate',
    description: 'Tahsildar office staff are demanding ₹5000 to issue a caste certificate required for a student applying for an educational scholarship.',
    category: 'Revenue Department',
    status: 'Pending',
    image: 'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800&q=80',
    rating: 88,
    date: '2023-10-24',
    tags: ['Bribery', 'Certificates', 'Extortion'],
    metadata: { location: 'Pathanamthitta', evidenceCount: 1, blockchainHash: '0x7d...2f3b', riskLevel: 'Medium' }
  }
];

export const activity = [
  { id: 'act-1', date: '2023-10-24T10:30:00Z', title: 'Complaint Submitted', body: 'New complaint cmp-030 registered anonymously.', status: 'Pending', user: 'System' },
  { id: 'act-2', date: '2023-10-24T10:35:00Z', title: 'AI Analysis Complete', body: 'Credibility score 88 assigned. Risk level: Medium.', status: 'Processed', user: 'AI Engine' },
  { id: 'act-3', date: '2023-10-23T14:20:00Z', title: 'Status Updated', body: 'Complaint cmp-001 moved to Investigating.', status: 'Investigating', user: 'Dr. Rajesh Kumar' },
  { id: 'act-4', date: '2023-10-23T15:00:00Z', title: 'Evidence Uploaded', body: 'Audio file (2.4MB) attached to cmp-001.', status: 'Verified', user: 'Citizen' },
  { id: 'act-5', date: '2023-10-22T09:15:00Z', title: 'Blockchain Hash Generated', body: 'Ledger updated for cmp-003. Hash: 0x1a...7b2c', status: 'Secured', user: 'System' },
  { id: 'act-6', date: '2023-10-21T11:00:00Z', title: 'Case Assigned', body: 'Complaint cmp-004 assigned to Inspector Priya.', status: 'Assigned', user: 'Admin' },
  { id: 'act-7', date: '2023-10-20T16:45:00Z', title: 'Field Visit Logged', body: 'Investigator visited site for cmp-006 in Alappuzha.', status: 'Investigating', user: 'Inspector Priya' },
  { id: 'act-8', date: '2023-10-19T10:20:00Z', title: 'Status Updated', body: 'Complaint cmp-002 marked as Resolved.', status: 'Resolved', user: 'Dr. Rajesh Kumar' },
  { id: 'act-9', date: '2023-10-18T14:10:00Z', title: 'Duplicate Detected', body: 'AI flagged potential duplicate for cmp-015.', status: 'Flagged', user: 'AI Engine' },
  { id: 'act-10', date: '2023-10-17T09:30:00Z', title: 'Report Generated', body: 'Monthly summary report generated for PWD.', status: 'Processed', user: 'System' },
  { id: 'act-11', date: '2023-10-16T11:45:00Z', title: 'Evidence Rejected', body: 'Image upload for cmp-020 rejected (unclear).', status: 'Rejected', user: 'Dr. Rajesh Kumar' },
  { id: 'act-12', date: '2023-10-15T13:20:00Z', title: 'Complaint Submitted', body: 'New complaint cmp-010 registered.', status: 'Pending', user: 'Citizen' },
  { id: 'act-13', date: '2023-10-14T15:50:00Z', title: 'AI Alert Triggered', body: 'High risk pattern detected in Revenue Dept (Kottayam).', status: 'Alert', user: 'AI Engine' },
  { id: 'act-14', date: '2023-10-13T10:05:00Z', title: 'Case Reopened', body: 'New evidence submitted for closed case cmp-011.', status: 'Investigating', user: 'Admin' },
  { id: 'act-15', date: '2023-10-12T16:30:00Z', title: 'Status Updated', body: 'Complaint cmp-012 moved to Investigating.', status: 'Investigating', user: 'Dr. Rajesh Kumar' },
  { id: 'act-16', date: '2023-10-11T09:15:00Z', title: 'Blockchain Sync', body: 'Daily ledger synchronization complete.', status: 'Secured', user: 'System' },
  { id: 'act-17', date: '2023-10-10T14:40:00Z', title: 'User Registered', body: 'New investigator profile created.', status: 'Processed', user: 'Admin' },
  { id: 'act-18', date: '2023-10-09T11:25:00Z', title: 'Evidence Uploaded', body: 'Document scan (1.1MB) attached to cmp-018.', status: 'Verified', user: 'Citizen' },
  { id: 'act-19', date: '2023-10-08T15:10:00Z', title: 'Case Assigned', body: 'Complaint cmp-018 assigned to Special Task Force.', status: 'Assigned', user: 'Director General' },
  { id: 'act-20', date: '2023-10-07T10:55:00Z', title: 'Status Updated', body: 'Complaint cmp-025 moved to Investigating.', status: 'Investigating', user: 'Inspector Priya' },
  { id: 'act-21', date: '2023-10-06T13:30:00Z', title: 'AI Analysis Complete', body: 'Credibility score 96 assigned to cmp-012.', status: 'Processed', user: 'AI Engine' },
  { id: 'act-22', date: '2023-10-05T09:45:00Z', title: 'Complaint Submitted', body: 'New complaint cmp-012 registered.', status: 'Pending', user: 'Citizen' },
  { id: 'act-23', date: '2023-10-04T16:20:00Z', title: 'Field Visit Logged', body: 'Site inspection completed for cmp-029.', status: 'Investigating', user: 'Dr. Rajesh Kumar' },
  { id: 'act-24', date: '2023-10-03T11:10:00Z', title: 'Status Updated', body: 'Complaint cmp-026 moved to Investigating.', status: 'Investigating', user: 'Admin' },
  { id: 'act-25', date: '2023-10-02T14:05:00Z', title: 'Blockchain Hash Generated', body: 'Ledger updated for cmp-029. Hash: 0x4c...1e8a', status: 'Secured', user: 'System' },
  { id: 'act-26', date: '2023-10-01T10:00:00Z', title: 'Complaint Submitted', body: 'New complaint cmp-029 registered.', status: 'Pending', user: 'Citizen' },
  { id: 'act-27', date: '2023-09-30T15:30:00Z', title: 'AI Alert Triggered', body: 'Critical risk pattern detected in Ernakulam.', status: 'Alert', user: 'AI Engine' },
  { id: 'act-28', date: '2023-09-29T09:15:00Z', title: 'Evidence Uploaded', body: 'Video file (15MB) attached to cmp-008.', status: 'Verified', user: 'Citizen' },
  { id: 'act-29', date: '2023-09-28T14:45:00Z', title: 'Complaint Submitted', body: 'New complaint cmp-008 registered.', status: 'Pending', user: 'Citizen' },
  { id: 'act-30', date: '2023-09-27T11:20:00Z', title: 'Status Updated', body: 'Complaint cmp-016 moved to Investigating.', status: 'Investigating', user: 'Dr. Rajesh Kumar' }
];

export const featuredItems = [
  primaryItems[0],
  primaryItems[3],
  primaryItems[11],
  primaryItems[15],
  primaryItems[25],
  primaryItems[28]
];

export const savedItems = [
  primaryItems[2],
  primaryItems[6],
  primaryItems[8],
  primaryItems[12],
  primaryItems[14],
  primaryItems[18],
  primaryItems[21],
  primaryItems[29]
];

// Helper Functions
export const getById = (id) => primaryItems.find(item => item.id === id);
export const getByCategory = (cat) => primaryItems.filter(item => item.category === cat);
export const filterByStatus = (status) => primaryItems.filter(item => item.status === status);
export const getRelated = (id) => {
  const item = getById(id);
  if (!item) return [];
  return primaryItems
    .filter(i => i.id !== id && (i.category === item.category || i.tags.some(t => item.tags.includes(t))))
    .slice(0, 3);
};