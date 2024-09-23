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
        response_list_targets = events_client.list_targets_by_rule(
            Rule=event_rule_name
        )

        targets = response_list_targets.get('Targets', [])
        target_ids = [target['Id'] for target in targets]

        if target_ids:
            # Remove all targets associated with the rule
            response_remove_targets = events_client.remove_targets(
                Rule=event_rule_name,
                Ids=target_ids
            )
            print(f"Removed all targets from rule: {event_rule_name}")
            print(f"Remove targets response: {response_remove_targets}")
        else:
            print(f"No targets found for rule: {event_rule_name}")

        # Delete the rule after removing the targets
        response_delete_rule = events_client.delete_rule(
            Name=event_rule_name
        )
        print(f"Deleted event rule: {event_rule_name}")
        print(f"Delete rule response: {response_delete_rule}")

        # Send success message to SNS
        message = (
            "WARNING: An infinite loop was detected, so your S3 event rule was deleted "
            "to avoid infinite Step Function invocations. Please follow the instructions "
            "in the README to ensure you did not accidentally create an infinite loop."
        )

        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject="S3 Event Rule Deleted - Infinite Loop Prevention"
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
            Subject="S3 Event Rule Deletion Failed"
        )
        print(f"Error message sent to SNS topic: {sns_topic_arn}")
        
        # Re-raise the error to mark the Lambda invocation as failed
        raise error
