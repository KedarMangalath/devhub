# Repo Map: vigilance

- Fingerprint: ecaeeea8eebf4d3d159daadc0a4df9ce2c88c152
- Indexed files: 47

## Top Directories
- `src`: 42 files
- `.`: 5 files

## Important Files
- `src/App.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 27 lines. Primary symbol: App. Key imports: import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';, import Layout from './components/Layout';, import Home from './pages/Home';, import SubmitComplaint from './pages/SubmitComplaint';, import TrackComplaint from './pages/TrackComplaint';.
- `vite.config.js`: Build or bundling configuration that tells the toolchain how to compile, package, or emit artifacts for this project. It has about 9 lines. Key imports: import { defineConfig } from 'vite';, import react from '@vitejs/plugin-react';.
- `package.json`: Node package manifest defining runtime metadata, scripts, dependencies, and package-manager behavior for the repo or workspace. It has about 25 lines. Top-level keys: name, private, version, type, scripts, dependencies.
- `src/main.jsx`: Reusable UI component responsible for part of the interface. It has about 10 lines. Key imports: import React from 'react';, import ReactDOM from 'react-dom/client';, import App from './App.jsx';, import './index.css';.
- `postcss.config.js`: Source file that contributes to the project root area of the repository. It has about 6 lines.
- `tailwind.config.js`: Source file that contributes to the project root area of the repository. It has about 21 lines.
- `src/components/AppShell.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 184 lines. Primary symbol: AppShell. Key imports: import React, { useState, useEffect } from 'react';, import { NavLink, Link, useLocation, Outlet } from 'react-router-dom';, import {, import { currentUser } from '../mockData';, import Footer from './shared/Footer';. Representative commands: Shield,.
- `src/pages/FileComplaintWorkflow.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 224 lines. Primary symbol: FileComplaintWorkflow. Key imports: import { useState } from 'react', import Navbar from '../components/shared/Navbar', import Footer from '../components/shared/Footer', import StepIndicator from '../components/file-complaint/StepIndicator', import DepartmentSelector from '../components/file-complaint/DepartmentSelector'.
- `src/components/Layout.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 95 lines. Primary symbol: Layout. Key imports: import { Outlet, Link, useLocation } from 'react-router-dom';, import { Shield, FileText, Search, LayoutDashboard, BarChart3, Menu } from 'lucide-react';, import { useState } from 'react';.
- `src/components/shared/Navbar.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 117 lines. Primary symbol: Navbar. Key imports: import { Link, useLocation } from 'react-router-dom', import { Shield, Menu, X } from 'lucide-react', import { useState } from 'react', import { cn } from '../../utils/cn'.
- `src/components/TabbedPanel.jsx`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 133 lines. Primary symbol: TabbedPanel. Key imports: import React from 'react';, import { cn } from '../utils/cn.js';.
- `src/pages/OfficerComplaintDetail.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 265 lines. Primary symbol: OfficerComplaintDetail. Key imports: import { useState } from 'react', import { useParams, useNavigate, Link } from 'react-router-dom', import Navbar from '../components/shared/Navbar', import StatusPill from '../components/shared/StatusPill', import AIPanel from '../components/officer/AIPanel'.
- `src/components/file-complaint/ReviewSubmitCard.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 122 lines. Primary symbol: ReviewSubmitCard. Key imports: import React from 'react';, import { ShieldCheck } from 'lucide-react';.
- `src/pages/ComplaintDetail.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 214 lines. Primary symbol: ComplaintDetail. Key imports: import { useState, useEffect } from 'react';, import { useParams, useNavigate } from 'react-router-dom';, import { api } from '../services/api';, import { StatusBadge, SeverityBadge } from '../components/Badges';, import { BrainCircuit, Shield, FileText, Clock, Link as LinkIcon, UserX, UserCheck, AlertTriangle, CheckCircle } from 'lucide-react';.
- `src/pages/DirectorAnalytics.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 130 lines. Primary symbol: DirectorAnalytics. Key imports: import React, { useMemo } from 'react';, import Navbar from '../components/shared/Navbar';, import MetricCard from '../components/shared/MetricCard';, import GeographicHeatmap from '../components/director/GeographicHeatmap';, import RiskProfileTable from '../components/director/RiskProfileTable';.
- `src/pages/OfficerDashboard.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 137 lines. Primary symbol: OfficerDashboard. Key imports: import { useState, useEffect } from 'react';, import { Link } from 'react-router-dom';, import { api } from '../services/api';, import { StatusBadge, SeverityBadge } from '../components/Badges';, import { Filter, Search, AlertCircle, BrainCircuit } from 'lucide-react';.
- `src/pages/PublicHome.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 22 lines. Primary symbol: PublicHome. Key imports: import React from 'react', import Navbar from '../components/shared/Navbar', import Footer from '../components/shared/Footer', import HeroSection from '../components/home/HeroSection', import FeatureCards from '../components/home/FeatureCards'.
- `src/pages/TrackComplaint.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 139 lines. Primary symbol: TrackComplaint. Key imports: import { useState, useEffect } from 'react';, import { useSearchParams } from 'react-router-dom';, import { api } from '../services/api';, import { StatusBadge } from '../components/Badges';, import { Search, CheckCircle2, Clock, AlertTriangle, Link as LinkIcon } from 'lucide-react';.
- `src/pages/AnalyticsDashboard.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 130 lines. Primary symbol: AnalyticsDashboard. Key imports: import { useState, useEffect } from 'react';, import { api } from '../services/api';, import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';, import { Map, AlertTriangle, TrendingUp, Users } from 'lucide-react';.
- `src/pages/Home.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 76 lines. Primary symbol: Home. Key imports: import { Link } from 'react-router-dom';, import { ShieldAlert, Search, MessageSquare, Smartphone, Lock, BrainCircuit } from 'lucide-react';.
- `src/pages/SubmitComplaint.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 168 lines. Primary symbol: SubmitComplaint. Key imports: import { useState } from 'react';, import { useNavigate } from 'react-router-dom';, import { api } from '../services/api';, import { UploadCloud, ShieldCheck, AlertCircle, Loader2 } from 'lucide-react';.
- `src/services/api.js`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 90 lines. Primary symbol: delay. Key imports: import { initialComplaints, analyticsData } from '../mockData';.
- `src/components/Badges.jsx`: Reusable UI component responsible for part of the interface. It has about 35 lines. Primary symbol: colors. Key imports: import React from 'react';.
- `src/components/ItemCard.jsx`: Reusable UI component responsible for part of the interface. It has about 148 lines. Primary symbol: ItemCard. Key imports: import React from 'react', import { Calendar, ChevronRight, Tag, Hash, ArrowRight } from 'lucide-react', import StatusPill from './shared/StatusPill', import { cn } from '../utils/cn'.

## Project Instructions
- `.devhub/DEVHUB.md`

## Repo Tree
```text
vigilance/
|- .devhub/
|- src
|  |- components
|  |  |- director
|  |  |  |- GeographicHeatmap.jsx
|  |  |  `- RiskProfileTable.jsx
|  |  |- file-complaint
|  |  |  |- ComplaintForm.jsx
|  |  |  |- DepartmentSelector.jsx
|  |  |  |- EvidenceUploader.jsx
|  |  |  |- ReviewSubmitCard.jsx
|  |  |  `- StepIndicator.jsx
|  |  |- home
|  |  |  |- FeatureCards.jsx
|  |  |  |- HeroSection.jsx
|  |  |  `- StatCounter.jsx
|  |  |- officer
|  |  |  |- AIPanel.jsx
|  |  |  |- ComplaintDataGrid.jsx
|  |  |  |- EvidenceGallery.jsx
|  |  |  `- FilterTabs.jsx
|  |  |- shared
|  |  |  |- Footer.jsx
|  |  |  |- MetricCard.jsx
|  |  |  |- Navbar.jsx
|  |  |  `- StatusPill.jsx
|  |  |- track
|  |  |  |- BlockchainTimeline.jsx
|  |  |  `- TrackingSearch.jsx
|  |  |- AppShell.jsx
|  |  |- Badges.jsx
|  |  |- ItemCard.jsx
|  |  |- Layout.jsx
|  |  |- StatCard.jsx
|  |  |- TabbedPanel.jsx
|  |  `- TimelineList.jsx
|  |- pages
|  |  |- AnalyticsDashboard.jsx
|  |  |- ComplaintDetail.jsx
|  |  |- DirectorAnalytics.jsx
|  |  |- FileComplaintWorkflow.jsx
|  |  |- Home.jsx
|  |  |- OfficerComplaintDetail.jsx
|  |  |- OfficerDashboard.jsx
|  |  |- PublicHome.jsx
|  |  |- SubmitComplaint.jsx
|  |  `- TrackComplaint.jsx
|  |- services
|  |  `- api.js
|  |- App.jsx
|  |- index.css
|  |- main.jsx
|  `- mockData.js
|- index.html
|- package.json
|- postcss.config.js
|- tailwind.config.js
`- vite.config.js
```