"""
create_tables.py
================
Creates all required DynamoDB tables for the invest backend.
Run this once when setting up a new AWS account.

Usage:
    python create_tables.py          # create all missing tables
    python create_tables.py --check  # just check which tables exist
"""
import os
import sys
import time
import argparse
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

# ─────────────────────────────────────────────────────────────────────────────
# Table definitions
# Each entry: (table_name, pk_attr, pk_type, sk_attr, sk_type)
# pk_type / sk_type: "S" = String, "N" = Number, "B" = Binary
# ─────────────────────────────────────────────────────────────────────────────
TABLES = [
    # table_name               PK attr            PK  SK attr                      SK
    ("stock-page",             "SYMBOL#<sym>",    "S", "SNAPSHOT#<date>",           "S"),
    ("stock-chart",            "SYMBOL#<sym>",    "S", "CHART#<period>#<interval>", "S"),
    ("stock-financials",       "SYMBOL#<sym>",    "S", "FINANCIALS#<period_type>",  "S"),
    ("stock-earnings",         "SYMBOL#<sym>",    "S", "EARNINGS#<date>",           "S"),
    ("stock-dividend-summary", "SYMBOL#<sym>",    "S", "DIVIDEND_SUMMARY#<date>",   "S"),
    ("stock-headlines",        "SYMBOL#<sym>",    "S", "HEADLINES#<date>",          "S"),
    ("stock-competitors",      "SYMBOL#<sym>",    "S", "COMPETITORS#<date>",        "S"),
    ("stock-options",          "SYMBOL#<sym>",    "S", "OPTIONS#<expiry>",          "S"),
    ("stock-short-interest",   "SYMBOL#<sym>",    "S", "SHORT_INTEREST#<date>",     "S"),
    ("stock-meta",             "SYMBOL#<sym>",    "S", "META",                      "S"),
    ("bse-filling",            "SYMBOL#<sym>",    "S", "FILINGS#<date>",            "S"),
]


def get_client():
    return boto3.client("dynamodb", region_name=AWS_REGION)


def table_exists(client, name: str) -> bool:
    try:
        client.describe_table(TableName=name)
        return True
    except client.exceptions.ResourceNotFoundException:
        return False


def create_table(client, table_name, pk_attr, pk_type, sk_attr, sk_type):
    """Create a DynamoDB table with PAY_PER_REQUEST billing."""
    try:
        client.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": pk_attr, "KeyType": "HASH"},
                {"AttributeName": sk_attr, "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": pk_attr, "AttributeType": pk_type},
                {"AttributeName": sk_attr, "AttributeType": sk_type},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"  [CREATING] {table_name}  (PK={pk_attr}, SK={sk_attr})")
        return True
    except client.exceptions.ResourceInUseException:
        print(f"  [EXISTS]   {table_name}")
        return False
    except ClientError as e:
        print(f"  [ERROR]    {table_name}: {e}")
        return False


def wait_for_table(client, table_name, timeout=60):
    """Poll until table status is ACTIVE."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = client.describe_table(TableName=table_name)
            status = resp["Table"]["TableStatus"]
            if status == "ACTIVE":
                return True
            print(f"    waiting... ({status})")
            time.sleep(3)
        except Exception:
            time.sleep(3)
    print(f"    [TIMEOUT] {table_name} never became ACTIVE")
    return False


def main():
    parser = argparse.ArgumentParser(description="Create DynamoDB tables for the invest backend.")
    parser.add_argument("--check", action="store_true", help="Only check which tables exist, don't create")
    args = parser.parse_args()

    print(f"\nAWS Region: {AWS_REGION}\n")

    client = get_client()

    created = []
    skipped = []

    for (table_name, pk_attr, pk_type, sk_attr, sk_type) in TABLES:
        exists = table_exists(client, table_name)

        if args.check:
            status = "[EXISTS] " if exists else "[MISSING]"
            print(f"  {status}  {table_name}")
            continue

        if exists:
            print(f"  [EXISTS]   {table_name}  — skipping")
            skipped.append(table_name)
        else:
            ok = create_table(client, table_name, pk_attr, pk_type, sk_attr, sk_type)
            if ok:
                created.append(table_name)

    if args.check:
        return

    if created:
        print(f"\nWaiting for {len(created)} new table(s) to become ACTIVE...")
        for table_name in created:
            ok = wait_for_table(client, table_name)
            if ok:
                print(f"  [ACTIVE]   {table_name}")

    print(f"\n{'='*50}")
    print(f"  Created : {len(created)}")
    print(f"  Skipped : {len(skipped)}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
