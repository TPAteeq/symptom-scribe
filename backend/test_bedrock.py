"""Quick Bedrock connectivity test — run from inside backend/ with the venv."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "deepseek.v3.2")

print(f"Region : {REGION}")
print(f"Model  : {MODEL_ID}")
print()

client = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

try:
    response = client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": "Say 'OK' and nothing else."}]}],
        inferenceConfig={"maxTokens": 10},
    )
    text = response["output"]["message"]["content"][0]["text"]
    print(f"SUCCESS — model replied: {text!r}")
    sys.exit(0)
except ClientError as e:
    code = e.response["Error"]["Code"]
    msg = e.response["Error"]["Message"]
    print(f"FAIL — {code}: {msg}")
    sys.exit(1)
except Exception as e:
    print(f"FAIL — {type(e).__name__}: {e}")
    sys.exit(1)
