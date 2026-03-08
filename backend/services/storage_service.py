"""
DynamoDB-backed storage service for SymptomScribe.
Uses boto3 resource API for automatic Python type handling.
Pre-seeded with synthetic patient data on first run.
"""

import os
import decimal
import logging
from typing import List, Optional
from datetime import datetime, timedelta

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from config import (
    USE_MOCK_SERVICES, AWS_REGION,
    TABLE_PATIENTS, TABLE_APPOINTMENTS, TABLE_SESSIONS, TABLE_SUMMARIES
)
from models import (
    SymptomSession, AppointmentDetails, ClinicalSummary,
    SyntheticPatient, SessionStatus, ConversationExchange,
    AppointmentSummary, SeverityFlag
)

logger = logging.getLogger(__name__)


def _from_dynamodb(item):
    """Recursively convert DynamoDB Decimal types to native Python int/float."""
    if isinstance(item, dict):
        return {k: _from_dynamodb(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [_from_dynamodb(i) for i in item]
    elif isinstance(item, decimal.Decimal):
        return int(item) if item % 1 == 0 else float(item)
    return item


class StorageService:
    def __init__(self, dynamodb=None):
        if dynamodb is not None:
            self.dynamodb = dynamodb
            self._ensure_tables()
            self._clear_tables()
            self._seed_synthetic_data()
            return
        elif USE_MOCK_SERVICES:
            from moto import mock_aws
            os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
            os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
            os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
            self._mock = mock_aws()
            self._mock.start()
            self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        else:
            self.dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        self._ensure_tables()
        self._seed_synthetic_data()


    def _create_table_if_missing(self, **kwargs):
        try:
            table = self.dynamodb.create_table(**kwargs)
            table.wait_until_exists()  # Block until table is ACTIVE
        except ClientError as e:
            if e.response['Error']['Code'] not in ('ResourceInUseException', 'ResourceNotFoundException'):
                raise

    def _clear_tables(self):
        """Delete all items from every table (used for test isolation)."""
        for table_name, pk in [
            (TABLE_SESSIONS, 'session_id'),
            (TABLE_SUMMARIES, 'summary_id'),
            (TABLE_APPOINTMENTS, 'appointment_id'),
            (TABLE_PATIENTS, 'patient_id'),
        ]:
            table = self.dynamodb.Table(table_name)
            response = table.scan()
            for item in response.get('Items', []):
                table.delete_item(Key={pk: item[pk]})

    def _ensure_tables(self):
        self._create_table_if_missing(
            TableName=TABLE_PATIENTS,
            KeySchema=[{'AttributeName': 'patient_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'patient_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST',
        )
        self._create_table_if_missing(
            TableName=TABLE_APPOINTMENTS,
            KeySchema=[{'AttributeName': 'appointment_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'appointment_id', 'AttributeType': 'S'},
                {'AttributeName': 'doctor_id', 'AttributeType': 'S'},
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'doctor_id-index',
                'KeySchema': [{'AttributeName': 'doctor_id', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'},
            }],
            BillingMode='PAY_PER_REQUEST',
        )
        self._create_table_if_missing(
            TableName=TABLE_SESSIONS,
            KeySchema=[{'AttributeName': 'session_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'session_id', 'AttributeType': 'S'},
                {'AttributeName': 'appointment_id', 'AttributeType': 'S'},
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'appointment_id-index',
                'KeySchema': [{'AttributeName': 'appointment_id', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'},
            }],
            BillingMode='PAY_PER_REQUEST',
        )
        self._create_table_if_missing(
            TableName=TABLE_SUMMARIES,
            KeySchema=[{'AttributeName': 'summary_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'summary_id', 'AttributeType': 'S'},
                {'AttributeName': 'appointment_id', 'AttributeType': 'S'},
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'appointment_id-index',
                'KeySchema': [{'AttributeName': 'appointment_id', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'},
            }],
            BillingMode='PAY_PER_REQUEST',
        )

    def _seed_synthetic_data(self):
        """Pre-populate with synthetic patients and appointments if not already present."""
        patients_table = self.dynamodb.Table(TABLE_PATIENTS)
        response = patients_table.scan(Select='COUNT')
        if response['Count'] > 0:
            logger.info("Synthetic data already exists, skipping seed")
            return

        now = datetime.now()

        patients_data = [
            {
                "patient_id": "patient_001",
                "name": "Sarah Johnson",
                "age": 34,
                "gender": "Female",
                "appointment_id": "appt_001",
                "appointment_time": now + timedelta(hours=2),
                "doctor_id": "doctor_001",
                "medical_history": ["Seasonal allergies", "Mild asthma"],
            },
        ]

        for p in patients_data:
            patient = SyntheticPatient(**p)
            self.dynamodb.Table(TABLE_PATIENTS).put_item(
                Item=patient.model_dump(mode='json')
            )

            appointment = AppointmentDetails(
                appointment_id=p["appointment_id"],
                patient_id=p["patient_id"],
                doctor_id=p["doctor_id"],
                appointment_time=p["appointment_time"],
                appointment_type="Telehealth General Consultation",
                status="scheduled",
            )
            self.dynamodb.Table(TABLE_APPOINTMENTS).put_item(
                Item=appointment.model_dump(mode='json')
            )

        logger.info(f"Seeded {len(patients_data)} synthetic patients and appointments")

    # --- Session CRUD ---

    def create_session(self, session_id: str, patient_id: str, appointment_id: str) -> SymptomSession:
        session = SymptomSession(
            session_id=session_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            status=SessionStatus.INITIALIZING,
            start_time=datetime.now(),
            conversation_history=[],
            emergency_detected=False,
            summary_generated=False,
        )
        self.dynamodb.Table(TABLE_SESSIONS).put_item(Item=session.model_dump(mode='json'))
        logger.info(f"Created session {session_id} for patient {patient_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SymptomSession]:
        response = self.dynamodb.Table(TABLE_SESSIONS).get_item(
            Key={'session_id': session_id}
        )
        item = response.get('Item')
        if item is None:
            return None
        return SymptomSession.model_validate(_from_dynamodb(item))

    def update_session(self, session: SymptomSession) -> None:
        self.dynamodb.Table(TABLE_SESSIONS).put_item(Item=session.model_dump(mode='json'))

    def add_exchange(self, session_id: str, exchange: ConversationExchange) -> None:
        self.dynamodb.Table(TABLE_SESSIONS).update_item(
            Key={'session_id': session_id},
            UpdateExpression='SET conversation_history = list_append(conversation_history, :new)',
            ExpressionAttributeValues={':new': [exchange.model_dump(mode='json')]},
        )

    # --- Appointment access ---

    def get_appointment(self, appointment_id: str) -> Optional[AppointmentDetails]:
        response = self.dynamodb.Table(TABLE_APPOINTMENTS).get_item(
            Key={'appointment_id': appointment_id}
        )
        item = response.get('Item')
        if item is None:
            return None
        return AppointmentDetails.model_validate(_from_dynamodb(item))

    def get_all_appointments(self) -> List[AppointmentDetails]:
        response = self.dynamodb.Table(TABLE_APPOINTMENTS).scan()
        return [AppointmentDetails.model_validate(_from_dynamodb(item)) for item in response.get('Items', [])]

    def store_appointment(self, appointment: AppointmentDetails) -> None:
        self.dynamodb.Table(TABLE_APPOINTMENTS).put_item(Item=appointment.model_dump(mode='json'))

    def get_appointments_by_doctor(self, doctor_id: str) -> List[AppointmentDetails]:
        response = self.dynamodb.Table(TABLE_APPOINTMENTS).query(
            IndexName='doctor_id-index',
            KeyConditionExpression=Key('doctor_id').eq(doctor_id),
        )
        return [AppointmentDetails.model_validate(_from_dynamodb(item)) for item in response.get('Items', [])]

    def get_patient(self, patient_id: str) -> Optional[SyntheticPatient]:
        response = self.dynamodb.Table(TABLE_PATIENTS).get_item(
            Key={'patient_id': patient_id}
        )
        item = response.get('Item')
        if item is None:
            return None
        return SyntheticPatient.model_validate(_from_dynamodb(item))

    # --- Summary CRUD ---

    def store_summary(self, summary: ClinicalSummary) -> None:
        self.dynamodb.Table(TABLE_SUMMARIES).put_item(Item=summary.model_dump(mode='json'))
        logger.info(f"Stored summary {summary.summary_id} for appointment {summary.appointment_id}")

    def get_summary(self, summary_id: str) -> Optional[ClinicalSummary]:
        response = self.dynamodb.Table(TABLE_SUMMARIES).get_item(
            Key={'summary_id': summary_id}
        )
        item = response.get('Item')
        if item is None:
            return None
        return ClinicalSummary.model_validate(_from_dynamodb(item))

    def get_summary_by_appointment(self, appointment_id: str) -> Optional[ClinicalSummary]:
        response = self.dynamodb.Table(TABLE_SUMMARIES).query(
            IndexName='appointment_id-index',
            KeyConditionExpression=Key('appointment_id').eq(appointment_id),
        )
        items = response.get('Items', [])
        if not items:
            return None
        return ClinicalSummary.model_validate(_from_dynamodb(items[0]))

    def get_summaries_by_doctor(self, doctor_id: str) -> List[ClinicalSummary]:
        appts = self.get_appointments_by_doctor(doctor_id)
        summaries = []
        for appt in appts:
            summary = self.get_summary_by_appointment(appt.appointment_id)
            if summary:
                summaries.append(summary)
        return summaries

    # --- Dashboard helpers ---

    def get_appointment_summaries_for_doctor(self, doctor_id: str) -> List[AppointmentSummary]:
        """Build AppointmentSummary list by joining appointments, patients, and summaries."""
        result = []
        for appt in self.get_appointments_by_doctor(doctor_id):
            patient = self.get_patient(appt.patient_id)
            summary = self.get_summary_by_appointment(appt.appointment_id)
            result.append(
                AppointmentSummary(
                    appointment_id=appt.appointment_id,
                    patient_name=patient.name if patient else "Unknown",
                    appointment_time=appt.appointment_time,
                    screening_completed=summary is not None,
                    summary_available=summary is not None,
                    severity_flag=summary.severity_flag if summary else None,
                )
            )
        return result


# Global singleton instance
storage = StorageService()
