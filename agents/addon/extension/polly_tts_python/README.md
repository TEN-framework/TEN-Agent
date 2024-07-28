## Amazon Polly TTS Extension

### Configurations

You can config this extension by providing following environments:

| Env | Required | Default | Notes |
| -- | -- | -- | -- |
| AWS_TTS_REGION | No | us-east-1 | The Region of Amazon Bedrock service you want to use. |
| AWS_TTS_ACCESS_KEY_ID | No | - | Access Key of your IAM User, make sure you've set proper permissions to [synthesize speech](https://docs.aws.amazon.com/polly/latest/dg/security_iam_id-based-policy-examples.html#example-managed-policy-service-admin). Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).  |
| AWS_TTS_SECRET_ACCESS_KEY | No | - | Secret Key of your IAM User, make sure you've set proper permissions to [synthesize speech](https://docs.aws.amazon.com/polly/latest/dg/security_iam_id-based-policy-examples.html#example-managed-policy-service-admin). Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html). |