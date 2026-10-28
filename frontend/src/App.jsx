import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Results from './pages/Results';
import Logs from './pages/Logs';
import Settings from './pages/Settings';
import { connectWS } from './api';

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
  const [wsEvents, setWsEvents] = useState([]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const ws = connectWS((msg) => {
      setWsEvents(prev => [msg, ...prev.slice(0, 99)]);
    });
    return () => ws.close();
  }, []);

  return (
    <BrowserRouter>
      <div className="app-layout">
        <nav className="sidebar">
          <div className="sidebar-header">
            <span className="logo-icon">⬡</span>
            <span className="logo-text">scraper</span>
          </div>
          <div className="nav-links">
            <NavLink to="/" end>Dashboard</NavLink>
            <NavLink to="/jobs">Jobs</NavLink>
            <NavLink to="/results">Results</NavLink>
            <NavLink to="/logs">Logs</NavLink>
            <NavLink to="/settings">Settings</NavLink>
          </div>
          <div className="sidebar-footer">
            <button
              className="theme-toggle"
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              aria-label="Toggle theme"
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {theme === 'dark' ? '☀' : '☽'}
            </button>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard wsEvents={wsEvents} />} />
            <Route path="/jobs" element={<Jobs wsEvents={wsEvents} />} />
            <Route path="/results" element={<Results />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
