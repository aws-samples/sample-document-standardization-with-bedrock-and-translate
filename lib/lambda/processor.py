import json

def handler(event, context):
    try:
        # Extract documentName from the event
        document_name = event['documentName']
        
        # Simulate processing logic
        print(f"Processing document: {document_name}")
        
        # If processing is successful
        return {
            'statusCode': 200,
            'body': f"{document_name} was successfully updated"
        }
    except Exception as e:
        # Handle any errors that might occur
        return {
            'statusCode': 500,
            'error': f"An error occurred processing {document_name}: {str(e)}",
            'documentName': document_name  # Ensure documentName is included in error output
        }
