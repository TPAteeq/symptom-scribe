import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import BookingPage from './components/BookingPage';
import VoiceInterface from './components/VoiceInterface';
import DoctorDashboard from './components/DoctorDashboard';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <header className="app-header">
          <h1>Symptom Scribe</h1>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<BookingPage />} />
            <Route path="/voice/:sessionId" element={<VoiceInterface />} />
            <Route path="/doctor/:doctorId" element={<DoctorDashboard />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;