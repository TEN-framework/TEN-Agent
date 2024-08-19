## Amazon Bedrock LLM Extension

### Configurations

You can config this extension by providing following environments:

| Env | Required | Default | Notes |
| -- | -- | -- | -- |
| AWS_REGION | No | us-east-1 | The Region of Amazon Bedrock service you want to use. |
| AWS_ACCESS_KEY_ID | No | - | Access Key of your IAM User, make sure you've set proper permissions to [invoke Bedrock models](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html) and gain [models access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) in Bedrock. Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).  |
| AWS_SECRET_ACCESS_KEY | No | - | Secret Key of your IAM User, make sure you've set proper permissions to [invoke Bedrock models](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html) and gain [models access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) in Bedrock. Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html). |
| AWS_BEDROCK_MODEL | No | Claude 3.5(anthropic.claude-3-5-sonnet-20240620-v1:0) | Bedrock model id, check [docuement](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html#model-ids-arns).  |