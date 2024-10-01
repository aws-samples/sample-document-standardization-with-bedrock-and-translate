# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import os

# Initialize AWS clients
events_client = boto3.client('events')
sns_client = boto3.client('sns')

# Environment variables
event_rule_name = os.environ.get('EVENT_RULE_NAME')
sns_topic_arn = os.environ.get('RESULTS_TOPIC_ARN')

def handler(event, context):
    try:
        # List all targets associated with the rule
        # response_list_targets = events_client.list_targets_by_rule(
        #     Rule=event_rule_name
        # )

        #targets = response_list_targets.get('Targets', [])
        #target_ids = [target['Id'] for target in targets]

        # if target_ids:
            # Remove all targets associated with the rule
        #     response_remove_targets = events_client.remove_targets(
        #         Rule=event_rule_name,
        #         Ids=target_ids
        #     )
        #     print(f"Removed all targets from rule: {event_rule_name}")
        #     print(f"Remove targets response: {response_remove_targets}")
        # else:
        #     print(f"No targets found for rule: {event_rule_name}")

        # Delete the rule after removing the targets
        response_disable_rule = events_client.disable_rule(
            Name=event_rule_name
        )

        print(f"Disabled event rule: {event_rule_name}")
        print(f"Disable rule response: {response_disable_rule}")

        # Send success message to SNS
        message = (
            '''WARNING: You have surpassed the alarm threshold for this workflow. You have either created an infinite loop to your Input S3 bucket, or you have tried to process too many documents at once.  Your S3 event rule was disabled to avoid excess Step Function invocations. Please follow the instructions in the README to either update the languages properly, or to increase the alarm threshold. You can re-enable after your changes have been made.'''
        )

        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject="S3 Event Rule Disabled"
        )
        print(f"Success message sent to SNS topic: {sns_topic_arn}")

    except Exception as error:
        print(f"Error occurred: {str(error)}")

        # Send error message to SNS
        error_message = (
            "Please check that you have not created an infinite loop. Your deleteS3EventRuleLambda "
            "was triggered but failed."
        )

        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=error_message,
            Subject="S3 Event Rule Disabling Failed"
        )
        print(f"Error message sent to SNS topic: {sns_topic_arn}")
        
        # Re-raise the error to mark the Lambda invocation as failed
        raise error




