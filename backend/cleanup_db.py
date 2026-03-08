"""
Clear all DynamoDB tables so the backend re-seeds fresh data on next startup.
Run from inside backend/: ./venv/bin/python cleanup_db.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

import boto3

region = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource(
    "dynamodb",
    region_name=region,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

tables = {
    os.getenv("TABLE_SUMMARIES", "symptom_scribe_summaries"): "summary_id",
    os.getenv("TABLE_SESSIONS", "symptom_scribe_sessions"): "session_id",
    os.getenv("TABLE_APPOINTMENTS", "symptom_scribe_appointments"): "appointment_id",
    os.getenv("TABLE_PATIENTS", "symptom_scribe_patients"): "patient_id",
}

for table_name, pk in tables.items():
    table = dynamodb.Table(table_name)
    response = table.scan()
    items = response.get("Items", [])
    for item in items:
        table.delete_item(Key={pk: item[pk]})
    print(f"Cleared {len(items)} items from {table_name}")

print("\nDone. Restart the backend to re-seed with fresh data.")
