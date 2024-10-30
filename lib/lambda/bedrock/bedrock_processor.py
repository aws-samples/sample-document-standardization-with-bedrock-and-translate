# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import boto3
from botocore.config import Config
import os
from docx import Document
from claude_prompt import get_claude_prompt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import mammoth
from bs4 import BeautifulSoup
from docx.shared import Pt
import zipfile
import tempfile
import shutil





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
        reference_key = 'word_template.docx'  
        output_bucket = os.environ['OUTPUT_BUCKET']  

        # Define local paths for temporary file storage
        # local_input_path = '/tmp/' + os.path.basename(document_key)
        # local_reference_path = '/tmp/' + os.path.basename(reference_key)
        # local_output_path_docx = '/tmp/' + os.path.basename(document_key).replace('.docx', '_corrected.docx')
        # tmp_dir = "/tmp/output_images"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_input:
            local_input_path = temp_input.name
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_reference:
            local_reference_path = temp_reference.name
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='_corrected.docx') as temp_output:
            local_output_path_docx = temp_output.name
        
        # Create a temporary directory
        tmp_dir = tempfile.mkdtemp(prefix='output_images_')
        

        # Download the DOCX file from S3 to the local path
        s3_client.download_file(bucket_name, document_key, local_input_path)

        # Download the reference template from S3 to the local path
        s3_client.download_file(bucket_name, reference_key, local_reference_path)

        # Extract images and replace them with placeholders
        images_info = extract_images_and_replace_with_placeholders(local_input_path, tmp_dir)
        
        #Convert DOCX to HTML using Mammoth
        html_content = docx_to_html(local_input_path)
        
        # Retrieve prompt from claude_prompt.py
        model_prompt = get_claude_prompt(html_content)

        # Send HTML to model for processing
        corrected_text = invoke_bedrock_model(model_prompt)

        # loading template and transforming HTML back to DOCX
        load_template_and_add_html_content(local_reference_path, local_output_path_docx, corrected_text)

        # reinstering images that were removed
        reinsert_images(local_output_path_docx, images_info)
        
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

        # # Cleanup local files
        # os.remove(local_input_path)
        # os.remove(local_output_path_docx)
        # os.remove(local_reference_path)

        # Clean up temporary files
        os.unlink(local_input_path)
        os.unlink(local_reference_path)
        os.unlink(local_output_path_docx)

        # Clean up temporary directory
        shutil.rmtree(tmp_dir)

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
    

## Functions used above##

def invoke_bedrock_model(model_prompt):
    """Invoke Bedrock model."""
    
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
    return corrected_text

def center_images(doc):
    """Center images in doc."""
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


def docx_to_html(docx_path):
    """Convert DOCX to HTML using Mammoth."""
    with open(docx_path, "rb") as docx_file:      
        html_content = mammoth.convert_to_html(docx_file).value
        return html_content


def _style_text(element, run):
    """Apply styles like bold and italic to a run."""
    # Apply bold and italic based on the element's tag
    if element.name in ['strong', 'b']:
        run.bold = True
    if element.name in ['em', 'i']:
        run.italic = True
    return run


def extract_images_and_replace_with_placeholders(docx_file_path, tmp_dir):
    """Extract images from Word document, save them to a temporary directory, and replace with placeholders."""
    doc = Document(docx_file_path)
    images_info = []
    image_counter = 1

    # Ensure tmp directory exists
    os.makedirs(tmp_dir, exist_ok=True)

    # Open the DOCX file as a ZIP archive to extract images
    with zipfile.ZipFile(docx_file_path, 'r') as docx_zip:
        # Loop through all paragraphs and runs to find images (graphics)
        for i, paragraph in enumerate(doc.paragraphs):
            for run in paragraph.runs:
                if 'graphic' in run.element.xml:
                    # Create a placeholder and file path for the image
                    placeholder = f'[IMAGE_{image_counter}]'
                    image_filename = f'image_{image_counter}.png'
                    image_path = os.path.join(tmp_dir, image_filename)

                    # Extract image data from the DOCX ZIP archive
                    for rel in doc.part.rels:
                        if "image" in doc.part.rels[rel].target_ref:
                            image = doc.part.rels[rel].target_part
                            image_bytes = image._blob

                            # Save the image to the temporary directory
                            with open(image_path, 'wb') as img_file:
                                img_file.write(image_bytes)

                            # Store the image information
                            images_info.append({
                                "placeholder": placeholder,
                                "image_path": image_path,
                                "paragraph_index": i
                            })

                            # Replace the image with a placeholder in the paragraph
                            paragraph.clear()
                            paragraph.add_run(placeholder)

                            image_counter += 1
                            break  # Stop after processing one image per run

    # Save the modified DOCX with placeholders
    doc.save(docx_file_path)
    return images_info


def reinsert_images(docx_file_path, images_info):
    """Reinsert images in place of placeholders in the Word document."""
    doc = Document(docx_file_path)
    for image_info in images_info:
        placeholder = image_info["placeholder"]
        print(f'placeholder : {placeholder}')
        image_path = image_info["image_path"]
        print(f'image_path : {image_path}')
        paragraph_index = image_info["paragraph_index"]

        # Loop through all paragraphs in the document
        for paragraph in doc.paragraphs:
            # Check if the placeholder exists in the paragraph
            if placeholder in paragraph.text:
                # Replace the placeholder with the image
                paragraph.clear()  # Clear the placeholder text
                run = paragraph.add_run()  # Create a new run to insert the image
                run.add_picture(image_path)  # Insert the image 

    # Save the final DOCX file with images reinserted
    doc.save(docx_file_path)

def _add_list(element, doc, level, list_type):
    """
    Recursively process ordered/unordered lists and apply styles based on nesting level.
    """
    # Select the appropriate list style based on the nesting level and list type
    if list_type == 'unordered':
        list_style = 'ListBullet' if level == 0 else f'ListBullet{level + 1}'  # ListBullet, ListBullet2, etc.
    else:
        list_style = 'ListNumber' if level == 0 else f'ListNumber{level + 1}'  # ListNumber, ListNumber2, etc.

    # Loop through the immediate children <li> elements of the current list
    for li in element.find_all('li', recursive=False):
        # Get the text for the current list item
        list_text = ""
        for child in li.children:
            if child.name is None:
                list_text += child.strip() + " "

        # Add the list item to the document with the correct style
        paragraph = doc.add_paragraph(list_text.strip(), style=list_style)

        # Process any nested <ul> or <ol> inside this <li> recursively
        nested_list = li.find(['ul', 'ol'])
        if nested_list:
            # Determine whether the nested list is ordered or unordered
            nested_list_type = 'unordered' if nested_list.name == 'ul' else 'ordered'
            _add_list(nested_list, doc, level + 1, nested_list_type)


def clear_document_body(doc):
    """Remove all content from the document body of the template while preserving headers, footers, and styles."""
    # Remove all paragraphs and content from the document body
    for paragraph in doc.paragraphs:
        p = paragraph._element
        p.getparent().remove(p)

    # Remove all tables, if any exist
    for table in doc.tables:
        tbl = table._element
        tbl.getparent().remove(tbl)

    return doc

def load_template_and_add_html_content(template_path, output_path, html_content):
    """Load a pre-styled template DOCX, add content from HTML, and save it to S3."""
    
    # Load the pre-styled template DOCX from S3
    doc = Document(template_path)

    # Clear the body of the template
    clear_document_body(doc)

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # HTML-to-DOCX mapping for common elements and styles in the template. Update as need (e.g. to handle tables)
    html_to_docx_mapping = {
        'p': lambda element, doc: doc.add_paragraph(element.text, style='Normal'),
        'ul': lambda element, doc: _add_list(element, doc, list_type='unordered', level=0),
        'ol': lambda element, doc: _add_list(element, doc, list_type='ordered', level=0),
        'strong': lambda element, doc: _style_text(element, doc.add_paragraph().add_run()), #bold
        'b': lambda element, doc: _style_text(element, doc.add_paragraph().add_run()), #bold
        'em': lambda element, doc: _style_text(element, doc.add_paragraph().add_run()), #italic
        'i': lambda element, doc: _style_text(element, doc.add_paragraph().add_run()) #italic
    }

    # Add all possible header levels
    html_to_docx_mapping.update({
        f'h{i}': lambda element, doc, i=i: doc.add_paragraph(element.text, style=f'Heading {i}') for i in range(1, 10)
    })

    # Iterate over all HTML elements and apply the mapping
    for element in soup:
        if element.name in html_to_docx_mapping:
            html_to_docx_mapping[element.name](element, doc)

    # Save the modified document to the output bucket
    doc.save(output_path)

