import boto3

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")  # Change region if needed
table = dynamodb.Table("stock-short-interest")

deleted = 0

print("Scanning table...")

response = table.scan()

with table.batch_writer() as batch:
    while True:
        for item in response["Items"]:
            # Replace these with your table's Primary Key names
            batch.delete_item(
                Key={
                    "SYMBOL#<sym>": item["SYMBOL#<sym>"],
                    "SI#<date>": item["SI#<date>"]
                }
            )
            deleted += 1

            if deleted % 100 == 0:
                print(f"Deleted {deleted} items...")

        if "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
        else:
            break

print(f"\nDone! Deleted {deleted} items.")