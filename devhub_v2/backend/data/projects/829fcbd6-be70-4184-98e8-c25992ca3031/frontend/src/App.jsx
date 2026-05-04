import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import SubmitComplaint from './pages/SubmitComplaint';
import TrackComplaint from './pages/TrackComplaint';
import AdminDashboard from './pages/AdminDashboard';
import AdminComplaints from './pages/AdminComplaints';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="submit" element={<SubmitComplaint />} />
          <Route path="track" element={<TrackComplaint />} />
          <Route path="admin" element={<AdminDashboard />} />
          <Route path="admin/complaints" element={<AdminComplaints />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;