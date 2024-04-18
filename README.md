# Document Processing Pipeline

This is a simple pipeline that will intake Word docx files, and correct any spelling, grammar and tone mistakes before outputting a corrected version of the document. Messages will be sent so users can be updated when the document correction process succeeds or fails. 

## Deploying the Solution
1. Create a new environment in Cloud9 with an m5.large instance.
2. Clone the repo
    ```git clone https://github.com/nadhya-p/DocProcessing```
3. From the root of the directory run the following commands: 

    ```cd DocProcessing/``` 
    ```npm install```
     ```cdk synth```
    ```cdk deploy```
    
4. Make any relevant changes to the styling of the ```custom-reference.docx``` doc (you will need to open it in Word and then upload the file to the input S3 bucket after you've made the changes).
    * Any changes you make will need to be made via the Style panes tab in order to propogate to the final output docx. Just changing text size / color will not work.

## Subscribing to the SNS Topic
After the solution is deployed, an SNS topic will be created. Create a subscription to this topic using a protocol and endpoint of your choice (this can be done via the AWS Management console). Make sure to confirm the subscription before testing the workflow.

## Request Access to Claude
If you have not already, request access to Claudev2.1 via the Amazon Bedrock Console

##Assumptions

This workflow assumes the following:
* You are uploading a docx file
* You would like a docx file as your final output
* Your document has a Title and Subtitle, with no body text above them.
* If your document only has a title update the ```extract_first_two_paragraphs(local_input_path)``` function accordingly.
* If your title is in Header 1 format, remove the following lines of code: 
    * ```title, subtitle = extract_first_two_paragraphs(local_input_path)```
    * ```subtitle_para = doc.paragraphs[0].insert_paragraph_before(subtitle, style='Subtitle')```
    * ```title_para = doc.paragraphs[0].insert_paragraph_before(title, style='Title')```

##Things to update
1. provide commands for uploading to s3
2. try deploying in another account to see if it works

## to check
* do people need to run:
```docker build -t lambda-layer-builder .
docker create --name lambda-layer-extractor lambda-layer-builder
docker cp lambda-layer-extractor:/output/layer.zip .
docker rm lambda-layer-extractor```
