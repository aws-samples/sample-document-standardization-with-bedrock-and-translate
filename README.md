# Document Processing Pipeline

This is a simple pipeline that will intake Word docx files, and correct any spelling, grammar and tone mistakes before outputting a corrected version of the document. Messages will be sent so users can be updated when the document correction process succeeds or fails. 

## Deploying the Solution
1. Create a new environment in Cloud9 with an m5.large instance.
2. Clone the repo
    ```bash
    git clone https://github.com/nadhya-p/DocProcessing
    ```
3. Run the following commands: 

    ```bash
    cd DocProcessing/
    npm install
    cdk synth
    cdk deploy
    ```

## Create a template for the output doc
In the repo you will find a _customer-reference.docx_. This document contains the styling configuration for the documents that this pipeline will create. If you want to follow certain styling considerations (e.g. all text with header 2 styling has blue font color or a company logo should be in the header of every page) you can update _customer-reference.docx_ accordingly.
**Note:** Any changes you make will need to be made via the Style panes tab of the Word docx. Just changing text size / color of the text will not work.

Once you have updated the _customer-reference.docx_ to your liking, upload it to the _docprocessingstack-inputbucket_ created by CloudFormation.

## Subscribing to the SNS Topic
After the solution is deployed, an SNS topic will be created. Create a subscription to this topic using a protocol and endpoint of your choice. Make sure to confirm the subscription before testing the workflow.

## Request Access to Claude
If you have not already, request access to Claudev2.1 via the Amazon Bedrock Console.

## Triggering the Workflow
Upload a Word doxc of your choice to the _docprocessingstack-inputbucket_ S3 bucket. The document will be processed and the corrected version will be added to the _docprocessingstack-outputbucket_. You will receive and SNS notification when this process is complete.


## Assumptions
This workflow assumes the following:
* You are uploading a docx file
* You would like a docx file as your final output
* Your document has a Title and Subtitle, with no body text above them.
* If your document only has a title, update the ```extract_first_two_paragraphs(local_input_path)``` function accordingly.
* If your title is in Header 1 format, remove the following lines of code: 
    * ```title, subtitle = extract_first_two_paragraphs(local_input_path)```
    * ```subtitle_para = doc.paragraphs[0].insert_paragraph_before(subtitle, style='Subtitle')```
    * ```title_para = doc.paragraphs[0].insert_paragraph_before(title, style='Title')```
* You are using Bedrock models located in eu-central-1. If not, change the region in the _processor.py_ file.

## Changing Output Format
This project uses [pandoc](https://pandoc.org/) to create HTML and .docx outputs. However, you can change your output file to be any file type that is supported by pandoc.
