# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import boto3
from botocore.config import Config
import os
import subprocess
from docx import Document
from prompt import get_claude_prompt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import zipfile
import mammoth
from bs4 import BeautifulSoup
from io import BytesIO
import base64
from docx.shared import Pt, RGBColor





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
       # document_key = event['path']  
        document_key = 'english/tone_test.docx'
        output_bucket = os.environ['OUTPUT_BUCKET']  



        # Define local paths for temporary file storage
        local_input_path = '/tmp/' + os.path.basename(document_key)
        local_output_path_docx = '/tmp/' + os.path.basename(document_key).replace('.docx', '_corrected.docx')
        output_dir = "/tmp/output_images"


        # Download the DOCX files from S3 to the local path
        s3_client.download_file(bucket_name, document_key, local_input_path)
        print('file downloaded')

        #Convert DOCX to HTML using Mammoth
        html_content = docx_to_html(local_input_path, output_dir)
        print('html content generated with image tags pointing to image files')

        # HTML content with <img> tags pointing to images
        print(html_content)  

        modified_html, images_info = replace_base64_images_with_placeholders(html_content)

        
        # Retrieve prompt from claude_prompt.py
        model_prompt = get_claude_prompt(modified_html)

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

        print("corrected text")
        print(corrected_text)

        final_html = restore_base64_images_in_html(corrected_text, images_info)
        print('images restored, final html below')
        print(final_html)


        html_to_docx_with_images(final_html, local_output_path_docx)

        
        
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

        # Cleanup local files
        os.remove(local_input_path)
        os.remove(local_output_path_docx)

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

def docx_to_html(docx_path, output_dir):
    """Convert DOCX to HTML using Mammoth."""
    with open(docx_path, "rb") as docx_file:      
        html_content = mammoth.convert_to_html(docx_file).value
        return html_content
    

def html_to_docx(corrected_html, docx_file_path, output_dir):
    """Convert corrected HTML back to .docx and reinsert images."""
    doc = Document()
    soup = BeautifulSoup(corrected_html, "html.parser")

    # Loop through the HTML content and add text to the DOCX
    for element in soup:
        if element.name == 'p':
            # Add paragraphs to the DOCX
            paragraph = doc.add_paragraph(element.text)
        elif element.name == 'h1':
            doc.add_heading(element.text, level=1)
        elif element.name == 'h2':
            doc.add_heading(element.text, level=2)
        elif element.name == 'h3':
            doc.add_heading(element.text, level=3)
        elif element.name == 'h4':
            doc.add_heading(element.text, level=4)
        # elif element.name == 'img':
        #     # Handle the images
        #     image_filename = element['src'].split("/")[-1]  # Extract the image filename from the src attribute
        #     image_path = os.path.join(output_dir, image_filename)  # Get the full path to the saved image
        #     paragraph = doc.add_paragraph()
        #     run = paragraph.add_run()
        #     run.add_picture(image_path)

    # Save the new .docx file
    doc.save(docx_file_path)


def replace_base64_images_with_placeholders(html_content):
    """Replace Base64-encoded images with placeholders and store the image data."""
    soup = BeautifulSoup(html_content, "html.parser")
    images_info = []
    placeholder_counter = 1

    # Find all <img> tags and replace the Base64 data with placeholders
    for img_tag in soup.find_all("img"):
        # Extract the Base64 data from the 'src' attribute
        base64_data = img_tag['src']
        
        # Store the Base64 data with a corresponding placeholder
        images_info.append({
            "placeholder": f"[IMAGE_{placeholder_counter}]",
            "base64_data": base64_data
        })
        
        # Replace the 'src' attribute with the placeholder
        img_tag['src'] = f"[IMAGE_{placeholder_counter}]"
        placeholder_counter += 1

    # Return the modified HTML content and the stored image data
    return str(soup), images_info

def restore_base64_images_in_html(corrected_html, images_info):
    """Restore the Base64-encoded images using placeholders."""
    # Replace each placeholder with the corresponding Base64 data
    for image_info in images_info:
        placeholder = image_info["placeholder"]
        base64_data = image_info["base64_data"]

        # Replace the placeholder in the HTML with the original Base64 data
        corrected_html = corrected_html.replace(placeholder, base64_data)

    return corrected_html

def insert_image(element, doc):
    """Handle the insertion of images."""
    base64_data = element['src']
    image_data = base64.b64decode(base64_data.split(",")[1])
    image_stream = BytesIO(image_data)
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    run.add_picture(image_stream)  

def _style_heading(text, doc, level, font_size, color=None, italic=False):
    """Helper function to apply styling to headings (used in mapping)."""
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.font.size = Pt(font_size)
    
    if color:
        run.font.color.rgb = RGBColor(*color)  # Apply color if provided
    
    run.italic = italic  # Apply italic if specified

def html_to_docx_with_images(corrected_html, docx_file_path):
    """Convert corrected HTML back to .docx and reinsert Base64-encoded images."""
    doc = Document()
    soup = BeautifulSoup(corrected_html, "html.parser")

    # Inline styling for h1 and other elements in the mapping
    html_to_docx_mapping = {
        'p': lambda element, doc: doc.add_paragraph(element.text),
        'h1': lambda element, doc: _style_heading(element.text, doc, level=1, font_size=24, color=(0, 0, 255), italic=True),  # Blue, italic, larger font for h1
        'h2': lambda element, doc: _style_heading(element.text, doc, level=2, font_size=18),
        'h3': lambda element, doc: _style_heading(element.text, doc, level=3, font_size=16),
        'img': insert_image  # Insert images
    }

    # Iterate over all elements in the soup
    for element in soup:
        # Check if the element is in the mapping dictionary
        if element.name in html_to_docx_mapping:
            # Call the corresponding function (with styling, image handling, etc.)
            html_to_docx_mapping[element.name](element, doc)

    # Save the new .docx file
    doc.save(docx_file_path)