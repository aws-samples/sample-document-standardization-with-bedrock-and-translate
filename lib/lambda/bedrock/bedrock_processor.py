import json
import boto3
from botocore.config import Config
import os
import subprocess
from docx import Document
from claude_prompt import get_claude_prompt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Initialize S3 client
config = Config(connect_timeout=5, read_timeout=60, retries={"total_max_attempts": 20, "mode": "adaptive"})
s3_client = boto3.client('s3', config=config)

# Bedrock config
region = "us-east-1"
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=region,
    endpoint_url=f'https://bedrock-runtime.{region}.amazonaws.com',
    config=config)

def handler(event, context):
    try:
        # Retrieve bucket name and document key from the event object
        bucket_name = os.environ['INPUT_BUCKET']  
        document_key = event['path']  
        reference_key = 'custom-reference.docx'  
        output_bucket = os.environ['OUTPUT_BUCKET']  

        # Define local paths for temporary file storage
        local_input_path = '/tmp/' + os.path.basename(document_key)
        local_output_path_html = '/tmp/' + os.path.basename(document_key).replace('.docx', '_corrected.html')
        local_reference_path = '/tmp/' + reference_key
        local_output_path_docx = '/tmp/' + os.path.basename(document_key).replace('.docx', '_corrected.docx')

        # Download the DOCX files from S3 to the local path
        s3_client.download_file(bucket_name, document_key, local_input_path)
        s3_client.download_file(bucket_name, reference_key, local_reference_path)
        

        # Convert DOCX to HTML using Pandoc
        subprocess.run([
            'pandoc',
            local_input_path,
            '-o',
            local_output_path_html,
            '-t', 'html',
            '--extract-media=/tmp/media'  # Extract images to a temporary directory
        ], check=True)

        # Read the content of the converted HTML file
        with open(local_output_path_html, 'r') as f:
            HTML_content = f.read()
        
        # Retrieve prompt from claude_prompt.py
        model_prompt = get_claude_prompt(HTML_content)

        native_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 5000,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": model_prompt}],
                }
            ],
        }

        body = json.dumps(native_request)

        # Using Claude 3 Sonnet (update as needed)
        modelID = "anthropic.claude-3-sonnet-20240229-v1:0"
        
        response = bedrock.invoke_model(
            body=body,
            modelId=modelID,
        )

        response = json.loads(response.get("body").read())
        corrected_text = response["content"][0]["text"]

        # Write the corrected HTML content to a new file
        with open(local_output_path_html, 'w') as f:
            f.write(corrected_text)

        # Convert the corrected HTML content back to a Word document
        subprocess.run([
            'pandoc',
            local_output_path_html,
            '-o',
            local_output_path_docx,
            '-t', 'docx',
            '--resource-path=/tmp/media',  # Ensure Pandoc can find the extracted images
            '--reference-doc', local_reference_path
        ], check=True)
        
        # Load the corrected Word document
        doc = Document(local_output_path_docx)

        # Center all images in the document
        center_images(doc)

        # Save the modified document
        doc.save(local_output_path_docx)

        if document_key.endswith("_translated.docx"):
            final_doc_name = document_key.replace('_translated.docx', '_corrected.docx')
        else:
            final_doc_name = document_key.replace('.docx', '_corrected.docx')

        # Upload the corrected Word document to the specified output S3 bucket
        with open(local_output_path_docx, 'rb') as f:
            s3_client.upload_fileobj(f, output_bucket, final_doc_name)

        #Create presigned URL
        url = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': output_bucket,
                                                            'Key': final_doc_name},
                                                    ExpiresIn=3600)

        # Cleanup local files
        os.remove(local_input_path)
        os.remove(local_output_path_html)
        os.remove(local_output_path_docx)

        print(url)

        return {
            'statusCode': 200,
            'body': final_doc_name
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Could not process {document_key} due to the following error: {str(e)}')
        }

def extract_first_two_paragraphs(document_path):
    doc = Document(document_path)
    paragraphs = [p.text for p in doc.paragraphs[:2]]
    return paragraphs[0], paragraphs[1] if len(paragraphs) > 1 else ""

def center_images(doc):
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            if 'graphic' in run.element.xml:
                align_paragraph_center(paragraph)

def align_paragraph_center(paragraph):
    p = paragraph._element
    pPr = p.get_or_add_pPr()
    jc = OxmlElement('w:jc')
    jc.set(qn('w:val'), 'center')
    pPr.append(jc)
