import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createWalkIn, startSession } from '../services/api';

function BookingPage() {
  const [patientName, setPatientName] = useState('');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleBegin = async () => {
    const name = patientName.trim();
    if (!name) return;
    setStarting(true);
    setError(null);
    try {
      const { patient_id, appointment_id } = await createWalkIn(name);
      const result = await startSession(patient_id, appointment_id);
      navigate(`/voice/${result.session_id}`, { state: { patientName: name } });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start session');
      setStarting(false);
    }
  };

  return (
    <div className="booking-page">
      <h2>Start Visit</h2>

      {error && (
        <div style={{ color: '#dc2626', marginBottom: '1rem' }}>Error: {error}</div>
      )}

      <div className="appointment-card">
        <p style={{ marginBottom: '0.75rem', color: '#475569', fontSize: '0.9rem' }}>
          Enter the patient's name to begin the AI pre-visit check-in:
        </p>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            placeholder="Patient name"
            value={patientName}
            onChange={(e) => setPatientName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleBegin()}
            style={{
              flex: 1,
              padding: '0.5rem 0.75rem',
              border: '1px solid #cbd5e1',
              borderRadius: '6px',
              fontSize: '1rem',
            }}
          />
          <button
            className="btn btn-primary"
            onClick={handleBegin}
            disabled={!patientName.trim() || starting}
          >
            {starting ? 'Starting...' : 'Begin Check-in'}
          </button>
        </div>
      </div>

      <div style={{ marginTop: '2rem', textAlign: 'center' }}>
        <button className="btn btn-secondary" onClick={() => navigate('/doctor/doctor_001')}>
          View Doctor Dashboard
        </button>
      </div>
    </div>
  );
}

export default BookingPage;
