import json
import boto3
from botocore.config import Config
import os
import subprocess
import requests
from docx import Document

# Initialize S3 client with specific configurations
config = Config(connect_timeout=5, read_timeout=60, retries={"total_max_attempts": 20, "mode": "adaptive"})
s3_client = boto3.client('s3', config=config)

# Bedrock 
region = "eu-central-1"
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=region,
    endpoint_url=f'https://bedrock-runtime.{region}.amazonaws.com',
    config=config)

# Company logo path
company_logo_path = 'SansLogo.png'

def handler(event, context):
    try:
        # Retrieve bucket name and document key from the event object
        bucket_name = event['documentPath']  # Bucket where the DOCX file is stored
        document_key = event['documentName']  # Key for the DOCX file in the S3 bucket
        reference_key = 'custom-reference.docx'  # Key for the DOCX file in the S3 bucket
        output_bucket = os.environ['OUTPUT_BUCKET']  # Environment variable for the output bucket
        
        # Check if the object key is 'custom-reference.docx'
        if document_key == reference_key:
            return {
                'statusCode': 200,
                'body': json.dumps(f'Uploaded reference template, skipping...')
            }

        # Define local paths for temporary file storage
        local_input_path = '/tmp/' + os.path.basename(document_key)
        local_output_path_md = '/tmp/' + os.path.basename(document_key).replace('.docx', '_corrected.html')
        local_reference_path = '/tmp/' + reference_key

        local_output_path_docx = '/tmp/' + os.path.basename(document_key).replace('.docx', '_corrected.docx')

        # Download the DOCX file from S3 to the local path
        s3_client.download_file(bucket_name, document_key, local_input_path)
        s3_client.download_file(bucket_name, reference_key, local_reference_path)
        
        # Extract title and subtitle before conversion
        title, subtitle = extract_first_two_paragraphs(local_input_path)


        # Convert DOCX to Markdown using Pandoc
        subprocess.run([
            'pandoc',
            local_input_path,
            '-o',
            local_output_path_md,
            '-t', 'html'
        ], check=True)

        # Read the content of the converted Markdown file
        with open(local_output_path_md, 'r') as f:
            markdown_content = f.read()

        # Using Claude v2.1 (update as needed)
        modelID = "anthropic.claude-v2:1"

        prompt = f"""\n\nHuman: Correct any spelling or grammar mistake you see in the following text without changing any of the html formatting: \n\nAssistant:"""

        llm_model_args = {"prompt": prompt + " " + markdown_content, "max_tokens_to_sample": 5000,
                          "stop_sequences": [], "temperature": 0.0, "top_p": 0.9}

        body = json.dumps(llm_model_args)

        # The actual call to retrieve an answer from the model
        response = bedrock.invoke_model(
            body=body,
            modelId=modelID,
            accept='application/json',
            contentType='application/json'
        )

        # Assuming Bedrock returns corrected text in JSON response
        response = json.loads(response.get("body").read())
        corrected_text = response.get("completion")

        # Write the corrected Markdown content to a new file
        with open(local_output_path_md, 'w') as f:
            f.write(corrected_text)
        
        s3_client.upload_file(local_output_path_md, output_bucket, os.path.basename(local_output_path_md))


        # Convert the corrected Markdown content back to a Word document
        subprocess.run([
            'pandoc',
            local_output_path_md,
            '-o',
            local_output_path_docx,
            '-t', 'docx',
            '--reference-doc', local_reference_path
        ], check=True)
        
        # Load the corrected Word document
        doc = Document(local_output_path_docx)
        
        # Remove the first paragraph if it starts with "Human: " (this removes Bedrock's response text from the top of the doc)
        if doc.paragraphs and doc.paragraphs[0].text.startswith("Human: "):
            p = doc.paragraphs[0]._element
            p.getparent().remove(p)
        
        # Add the title and subtitle back to the beginning of the document
        subtitle_para = doc.paragraphs[0].insert_paragraph_before(subtitle, style='Subtitle')
        title_para = doc.paragraphs[0].insert_paragraph_before(title, style='Title')

        # Save the modified document
        doc.save(local_output_path_docx)

        # Upload the corrected Word document to the specified output S3 bucket
        with open(local_output_path_docx, 'rb') as f:
            s3_client.upload_fileobj(f, output_bucket, local_output_path_docx.split('/')[-1])

        # Cleanup local files to free up space (optional but recommended)
        os.remove(local_input_path)
        os.remove(local_output_path_md)
        os.remove(local_output_path_docx)

        return {
            'statusCode': 200,
            'body': json.dumps(f'Grammar check was successful for {document_key}')
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Could not process {document_key}')
        }

def extract_first_two_paragraphs(document_path):
    """
    Extracts the first two paragraphs from a Word document.

    Args:
        document_path (str): The path to the Word document.

    Returns:
        tuple: A tuple containing the text of the first two paragraphs.
    """
    doc = Document(document_path)
    paragraphs = [p.text for p in doc.paragraphs[:2]]
    return paragraphs[0], paragraphs[1] if len(paragraphs) > 1 else ""