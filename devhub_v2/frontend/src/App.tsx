import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import ProjectView from './pages/ProjectView'
import { DevhubSettingsProvider } from './theme'

function App() {
  return (
    <DevhubSettingsProvider>
      <div className="app-scale-shell devhub-themed">
        <Router>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/project/:id" element={<ProjectView />} />
          </Routes>
        </Router>
      </div>
    </DevhubSettingsProvider>
  )
}

export default App
