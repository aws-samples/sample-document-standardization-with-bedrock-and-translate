import json

def handler(event, context):
    # Example processing logic
    print("Processing event:", event)
    
    # Example response
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
