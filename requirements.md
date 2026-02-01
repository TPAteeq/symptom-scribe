# Requirements Document

## Introduction

SymptomScribe is an AI-powered pre-visit symptom screening tool for telehealth that enables patients to complete voice-based symptom assessments before their appointments. The system conducts natural voice conversations with patients, generates structured clinical summaries for healthcare providers, and includes emergency detection capabilities. This is a demonstration system using synthetic data only and is not intended for actual medical use.

## Glossary

- **Patient**: A user who completes the pre-visit symptom screening
- **Doctor**: A healthcare provider who reviews generated clinical summaries
- **Voice_UI**: The browser-based voice conversation interface
- **AI_Agent**: The conversational AI system powered by Amazon Bedrock
- **Clinical_Summary**: A structured report containing chief complaint, symptom details, relevant history, and severity flag
- **Emergency_Keywords**: Predefined terms that trigger immediate emergency response (chest pain, can't breathe, unconscious, bleeding)
- **Symptom_Session**: A complete voice conversation between patient and AI agent
- **Severity_Flag**: A classification of symptom urgency (Low/Medium/High)
- **Transcription_Service**: AWS Transcribe for converting speech to text
- **Voice_Synthesis**: ElevenLabs service for converting text to speech

## Requirements

### Requirement 1: Appointment Booking and Pre-Visit Screen Entry

**User Story:** As a patient, I want to see an option to complete a pre-visit screen after booking my appointment, so that I can prepare my symptoms before seeing the doctor.

#### Acceptance Criteria

1. WHEN a patient confirms a doctor appointment, THE System SHALL display an option: "Complete a quick AI symptom check before your visit (takes 2-3 min)"
2. WHEN the patient clicks "Start AI Pre-Visit Screen," THE Voice_UI SHALL initialize and begin the symptom screening session
3. WHEN the patient declines the pre-visit screen, THE System SHALL proceed to the appointment without a symptom screening
4. THE System SHALL clearly indicate the estimated time commitment for the pre-visit screening
5. WHEN the pre-visit screen option is presented, THE System SHALL include appropriate disclaimers about the demonstration nature

### Requirement 2: Patient Voice Conversation

**User Story:** As a patient, I want to have a natural voice conversation about my symptoms, so that I can easily communicate my health concerns before my appointment.

#### Acceptance Criteria

1. WHEN a patient starts the AI Pre-Visit Screen, THE Voice_UI SHALL present an audio prompt asking "What is bothering you today?"
2. WHEN a patient speaks into their microphone, THE Transcription_Service SHALL convert speech to text in real-time
3. WHEN transcribed text is received, THE AI_Agent SHALL generate an appropriate follow-up question based on the patient's response
4. WHEN the AI generates a response, THE Voice_Synthesis SHALL convert the text response to natural-sounding speech
5. WHEN the conversation reaches 4-6 exchanges, THE AI_Agent SHALL conclude the session naturally
6. WHILE the conversation is active, THE Voice_UI SHALL provide clear visual feedback indicating listening, processing, and speaking states

### Requirement 3: Emergency Detection and Response

**User Story:** As a patient with urgent symptoms, I want the system to recognize emergency situations, so that I receive immediate guidance to seek emergency care.

#### Acceptance Criteria

1. WHEN a patient mentions emergency keywords (chest pain, can't breathe, unconscious, bleeding), THE Emergency_Detection SHALL trigger immediately using hardcoded rules
2. WHEN emergency detection is triggered, THE AI_Agent SHALL respond with "This sounds urgent. Please call emergency services or go to the nearest hospital right away."
3. WHEN an emergency is detected, THE Symptom_Session SHALL terminate immediately after delivering the emergency message
4. THE Emergency_Detection SHALL use only predefined keyword matching and SHALL NOT rely on AI interpretation
5. WHEN emergency keywords are detected, THE Clinical_Summary SHALL be marked with emergency flag before termination

### Requirement 4: Clinical Summary Generation

**User Story:** As a doctor, I want to receive structured clinical summaries of patient conversations, so that I can prepare effectively for appointments.

#### Acceptance Criteria

1. WHEN a symptom session completes normally, THE AI_Agent SHALL generate a Clinical_Summary within 5 seconds
2. THE Clinical_Summary SHALL contain Chief Complaint, Symptom Details, Relevant History, and Severity Flag sections
3. WHEN generating summaries, THE AI_Agent SHALL assign a Severity_Flag of Low, Medium, or High based on symptom assessment
4. THE Clinical_Summary SHALL be stored in persistent storage and associated with the patient's appointment
5. WHEN a Clinical_Summary is generated, THE Patient SHALL receive confirmation that their summary has been sent to their doctor

### Requirement 5: Doctor Dashboard Access

**User Story:** As a doctor, I want to access patient symptom summaries before appointments, so that I can review relevant information and prepare for consultations.

#### Acceptance Criteria

1. WHEN a doctor logs into the dashboard, THE System SHALL display a list of upcoming appointments with available summaries
2. WHEN a Clinical_Summary is available, THE Dashboard SHALL display the patient card with summary preview
3. WHEN a doctor clicks on a patient card, THE Dashboard SHALL display the complete Clinical_Summary
4. THE Dashboard SHALL allow doctors to read, dismiss, or print Clinical_Summaries
5. WHEN no summary is available for a patient, THE Dashboard SHALL indicate "No pre-visit screening completed"

### Requirement 6: Session Management and Data Storage

**User Story:** As a system administrator, I want patient conversations and summaries to be properly stored and managed, so that data integrity is maintained throughout the process.

#### Acceptance Criteria

1. WHEN a patient starts a symptom session, THE System SHALL create a unique Symptom_Session record with timestamp and patient identifier
2. WHEN conversation exchanges occur, THE System SHALL store each question-answer pair with the associated Symptom_Session
3. WHEN a Clinical_Summary is generated, THE System SHALL store it with reference to the originating Symptom_Session
4. THE System SHALL maintain conversation history for the duration of the patient's appointment
5. WHEN storing patient data, THE System SHALL use only synthetic data for demonstration purposes

### Requirement 7: Voice Interface User Experience

**User Story:** As a patient, I want a smooth and intuitive voice interface experience, so that I can focus on describing my symptoms without technical difficulties.

#### Acceptance Criteria

1. WHEN the Voice_UI loads, THE System SHALL request microphone permissions and provide clear instructions
2. WHILE the patient is speaking, THE Voice_UI SHALL display visual indicators showing active listening
3. WHEN the AI is processing, THE Voice_UI SHALL show processing status to indicate the system is working
4. WHEN the AI responds with voice, THE Voice_UI SHALL display the spoken text for accessibility
5. WHEN technical errors occur, THE Voice_UI SHALL provide clear error messages and recovery options
6. THE Voice_UI SHALL work in modern web browsers without requiring additional software installation

### Requirement 8: Real-time Audio Processing

**User Story:** As a patient, I want my speech to be processed quickly and accurately, so that the conversation flows naturally without long delays.

#### Acceptance Criteria

1. THE System SHALL maintain end-to-end response time (patient finishes speaking → patient hears AI response) under 3 seconds
2. WHEN a patient speaks, THE Transcription_Service SHALL process audio and provide text transcription
3. WHEN transcription is complete, THE AI_Agent SHALL generate appropriate responses based on the conversation context
4. THE System SHALL maintain WebSocket connections for real-time bidirectional audio streaming
5. WHEN network interruptions occur, THE System SHALL attempt to reconnect and resume the conversation

### Requirement 9: System Integration and Architecture

**User Story:** As a system architect, I want clear separation between voice processing, AI conversation management, and data storage components, so that the system is maintainable and scalable.

#### Acceptance Criteria

1. WHEN voice processing components are modified, THE AI conversation logic and data storage SHALL remain unaffected
2. WHEN AI conversation logic is updated, THE voice processing and storage components SHALL continue functioning unchanged
3. WHEN data storage implementations change, THE voice processing and AI components SHALL operate without modification
4. THE System SHALL use Amazon Bedrock for AI conversation management and clinical summary generation
5. THE System SHALL use AWS Transcribe for speech-to-text conversion and ElevenLabs for text-to-speech synthesis

### Requirement 10: Demonstration and Disclaimer Requirements

**User Story:** As a system user, I want clear indication that this is a demonstration system, so that I understand its limitations and appropriate use.

#### Acceptance Criteria

1. WHEN users access the system, THE Interface SHALL display prominent disclaimers stating "Demonstration only, not a medical device"
2. THE System SHALL clearly indicate that all patient data is synthetic and for demonstration purposes only
3. THE System SHALL display disclaimers that it is "Not a substitute for professional medical advice"
4. WHEN emergency detection occurs, THE System SHALL still recommend contacting emergency services despite being a demonstration
5. THE System SHALL include appropriate legal disclaimers about the demonstration nature of the tool

### Requirement 11: Performance and Reliability

**User Story:** As a patient, I want the system to respond quickly and reliably, so that my symptom screening experience is efficient and effective.

#### Acceptance Criteria

1. WHEN a patient completes a symptom session, THE Clinical_Summary SHALL be generated and stored within 5 seconds
2. THE Voice_UI SHALL support concurrent sessions from multiple patients without performance degradation
3. WHEN system components fail, THE System SHALL provide graceful error handling and user notification
4. THE System SHALL maintain 99% uptime during demonstration periods
5. WHEN high traffic occurs, THE System SHALL scale appropriately to maintain response times under 3 seconds