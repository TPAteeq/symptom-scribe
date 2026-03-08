import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDoctorDashboard } from '../services/api';
import type { DoctorDashboard as DashboardData, ClinicalSummary, AppointmentSummary } from '../types';

function DoctorDashboard() {
  const { doctorId } = useParams<{ doctorId: string }>();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [selectedSummary, setSelectedSummary] = useState<ClinicalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = () => {
    if (!doctorId) return;
    setLoading(true);
    getDoctorDashboard(doctorId)
      .then(setDashboard)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchDashboard();
  }, [doctorId]);

  const handleViewSummary = async (appt: AppointmentSummary) => {
    // Find the matching summary from completed screenings
    const matchingSummary = dashboard?.completed_screenings.find(
      (s) => s.appointment_id === appt.appointment_id
    );
    if (matchingSummary) {
      setSelectedSummary(matchingSummary);
    } else {
      // Try fetching by looking through all summaries
      setError('Summary not found');
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  if (error) {
    return (
      <div className="loading">
        <p style={{ color: '#dc2626' }}>Error: {error}</p>
        <button className="btn btn-secondary" onClick={fetchDashboard} style={{ marginTop: '1rem' }}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="doctor-dashboard">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Doctor Dashboard</h2>
        <div>
          <button className="btn btn-secondary" onClick={fetchDashboard} style={{ marginRight: '0.5rem' }}>
            Refresh
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/')}>
            Back to Appointments
          </button>
        </div>
      </div>

      <div className="dashboard-content">
        {/* Appointments Panel */}
        <div className="appointments-panel">
          <h3>Upcoming Appointments</h3>
          {dashboard?.upcoming_appointments.length === 0 && (
            <p style={{ color: '#64748b' }}>No upcoming appointments</p>
          )}
          {dashboard?.upcoming_appointments.map((appt) => (
            <div
              key={appt.appointment_id}
              className={`patient-card ${selectedSummary?.appointment_id === appt.appointment_id ? 'selected' : ''}`}
              onClick={() => appt.summary_available && handleViewSummary(appt)}
              style={{ cursor: appt.summary_available ? 'pointer' : 'default' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h4>{appt.patient_name}</h4>
                  <p>{new Date(appt.appointment_time).toLocaleString()}</p>
                </div>
                {appt.screening_completed && appt.severity_flag ? (
                  <span className={`severity-badge ${appt.severity_flag.toLowerCase()}`}>
                    {appt.severity_flag}
                  </span>
                ) : (
                  <span className="no-screening">No screening</span>
                )}
              </div>
              {appt.summary_available && (
                <p style={{ fontSize: '0.8rem', color: '#0891b2', marginTop: '0.5rem', fontWeight: 600 }}>
                  Click to view summary
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Summary Detail Panel */}
        <div>
          {selectedSummary ? (
            <div className="summary-detail">
              <h3>Clinical Summary</h3>

              {selectedSummary.emergency_flag && (
                <div style={{ background: '#fef2f2', border: '1px solid #dc2626', borderRadius: '8px', padding: '0.75rem', marginBottom: '1rem', color: '#991b1b', fontWeight: 600 }}>
                  Emergency Flag - Patient mentioned emergency symptoms
                </div>
              )}

              <section>
                <h4>Chief Complaint</h4>
                <p>{selectedSummary.chief_complaint}</p>
              </section>

              <section>
                <h4>Symptom Details</h4>
                {selectedSummary.symptom_details.map((sd, i) => (
                  <div key={i} style={{ marginBottom: '0.5rem', paddingLeft: '0.5rem', borderLeft: '3px solid #e2e8f0' }}>
                    <p><strong>{sd.symptom}</strong></p>
                    {sd.duration && <p>Duration: {sd.duration}</p>}
                    {sd.severity && <p>Severity: {sd.severity}</p>}
                    {sd.location && <p>Location: {sd.location}</p>}
                  </div>
                ))}
              </section>

              {selectedSummary.relevant_history.length > 0 && (
                <section>
                  <h4>Relevant History</h4>
                  <ul>
                    {selectedSummary.relevant_history.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                </section>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
                <div className={`severity-flag ${selectedSummary.severity_flag.toLowerCase()}`}>
                  Severity: {selectedSummary.severity_flag}
                </div>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  {selectedSummary.conversation_exchanges} exchanges
                </span>
              </div>
            </div>
          ) : (
            <div className="summary-detail" style={{ textAlign: 'center', color: '#64748b', padding: '3rem' }}>
              <p>Select a patient with a completed screening to view their clinical summary</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DoctorDashboard;
