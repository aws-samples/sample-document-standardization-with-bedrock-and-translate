import json


def handler(event, context):
    print(event)
    status_code = event.get('statusCode', None)

    if status_code != 200 and status_code != None:
        error = event.get('message', 'Unknown error')
        final_message = f"The workflow could not be completed due to the following error: {error}"
        return {
            'statusCode': 200,
            'message': final_message
        }

        return {
            'statusCode': 200,
            'message': final_message
        }
    else: 
        success_docs = []
        failure_docs = []
        
        map_results = event.get('mapResults', []) 
        payloads = [result['Payload'] for result in map_results]
        for payload in payloads:
            status_code = payload['statusCode']
            body = payload['body']
            
            if status_code == 200:
                success_docs.append(body)
            else:
                failure_docs.append(body)
            
        final_message = generate_email_content(success_docs, failure_docs)
        print(final_message)

        return {
            'statusCode': 200,
            'message': final_message
        }

def generate_email_content(success_docs, failure_docs):
    if success_docs:
        success_message = "The following documents were successfully processed and can be found in the output bucket:\n\n"
        for doc in success_docs:
            success_message += doc + "\n\n"
    else:
        success_message = "No documents were successfully processed."

    if failure_docs:
        failure_message = "The following documents could not be processed:\n\n"
        for doc in failure_docs:
            failure_message += doc + "\n\n"
    else:
        failure_message = "All documents were successfully processed."

    final_message = success_message + "\n\n" + failure_message
    return final_message