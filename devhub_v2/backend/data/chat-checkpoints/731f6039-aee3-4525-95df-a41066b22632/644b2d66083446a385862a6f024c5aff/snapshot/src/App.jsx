import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import SubmitComplaint from './pages/SubmitComplaint';
import TrackComplaint from './pages/TrackComplaint';
import OfficerDashboard from './pages/OfficerDashboard';
import ComplaintDetail from './pages/ComplaintDetail';
import AnalyticsDashboard from './pages/AnalyticsDashboard';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="submit" element={<SubmitComplaint />} />
          <Route path="track" element={<TrackComplaint />} />
          <Route path="officer" element={<OfficerDashboard />} />
          <Route path="officer/complaint/:id" element={<ComplaintDetail />} />
          <Route path="director" element={<AnalyticsDashboard />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;