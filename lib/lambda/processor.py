import json
import boto3
from botocore.config import Config
import os
import subprocess

# Initialize S3 client with specific configurations
config = Config(connect_timeout=5, read_timeout=60, retries={"total_max_attempts": 20, "mode": "adaptive"})
s3_client = boto3.client('s3', config=config)

def handler(event, context):
    # Retrieve bucket name and document key from the event object
    bucket_name = event['documentPath']  # Bucket where the DOCX file is stored
    document_key = event['documentName']  # Key for the DOCX file in the S3 bucket
    output_bucket = os.environ['OUTPUT_BUCKET']  # Environment variable for the output bucket

    # Define local paths for temporary file storage
    local_input_path = '/tmp/' + os.path.basename(document_key)
    local_output_path = '/tmp/' + os.path.basename(document_key).replace('.docx', '.md')

    # Download the DOCX file from S3 to the local path
    s3_client.download_file(bucket_name, document_key, local_input_path)

    # Convert DOCX to Markdown using Pandoc
    subprocess.run([
        'pandoc',
        local_input_path,
        '-o',
        local_output_path,
        '-t', 'markdown'
    ], check=True)

    # Upload the converted Markdown file to the specified output S3 bucket
    with open(local_output_path, 'rb') as f:
        s3_client.upload_fileobj(f, output_bucket, local_output_path.split('/')[-1])

    # Cleanup local files to free up space (optional but recommended)
    os.remove(local_input_path)
    os.remove(local_output_path)

    return {
        'statusCode': 200,
        'body': json.dumps('Conversion from DOCX to Markdown was successful')
    }
