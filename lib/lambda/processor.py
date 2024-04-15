import json
import boto3
from botocore.config import Config
from docx import Document
from io import BytesIO
import os


# Initialize Bedrock API client
config = Config(connect_timeout=5, read_timeout=60, retries={"total_max_attempts": 20, "mode": "adaptive"})
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='eu-central-1',
    endpoint_url='https://bedrock-runtime.eu-central-1.amazonaws.com',
    config=config
)

def handler(event, context):
    s3_client = boto3.client('s3', config=config)
    bucket_name = event['documentPath']  # Assuming 'documentPath' is the bucket name
    document_key = event['documentName']  # Assuming 'documentName' is the S3 key for the document

    # Fetch the Word document from S3
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=document_key)
        document_stream = BytesIO(response['Body'].read())
        doc = Document(document_stream)

        # Process each paragraph for corrections
        for paragraph in doc.paragraphs:
            corrected_text = correct_text(paragraph.text)
            paragraph.text = corrected_text

        # Save the corrected document back to a BytesIO object
        output_stream = BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)  # Rewind the stream to the beginning before uploading

        # Upload the processed document back to S3
        output_bucket = os.environ['OUTPUT_BUCKET']  
        output_key = 'corrected-' + document_key 
        s3_client.put_object(Body=output_stream.getvalue(), Bucket=output_bucket, Key=output_key)

        return {
            'statusCode': 200,
            'body': f"{document_key} was successfully updated and saved to {output_bucket}/{output_key}"
        }
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"An error occurred while processing {document_key}: {str(e)}"
        }

def correct_text(text):
    """ Call the Bedrock API to correct text with specific instructions. """
    model_id = "Anthropic-Claude-V2.1"
    accept = "*/*"
    content_type = "application/json"
    prompt = f"Please correct any grammar and spelling mistakes in the following text: '{text}'"
    parameters = {
        "temperature": 0.0,  # Very deterministic
        "top_p": 0.9  # Fairly high probability but allows some creativity
    }
    body = json.dumps({
        "inputs": prompt,
        "parameters": parameters
    })
    
    try:
        response = bedrock.invoke_model(
            body=body,
            modelId=model_id,
            accept=accept,
            contentType=content_type
        )
        
        response_body = json.loads(response.get("body").read())
        answer = get_llm_answer(model_id, response_body)
        return answer
    except Exception as e:
        print(f"An error occurred while correcting text with Bedrock API: {str(e)}")
        # Return original text in case of an API error to prevent data loss
        return text

def get_llm_answer(model_id, response):
    if model_id == "Ammazon-Titan-Express":
        return response.get('results')[0].get('outputText')
    elif model_id == "Anthropic-Claude-V2.1":
        return response.get("completion")
    elif model_id == "Anthropic-Claude-Instant":
        return response.get("completion")