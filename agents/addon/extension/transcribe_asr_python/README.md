## Amazon Transcribe ASR Extension

### Configurations

You can config this extension by providing following environments:

| Env | Required | Default | Notes |
| -- | -- | -- | -- |
| AWS_REGION | No | us-east-1 | The Region of Amazon Transcribe service you want to use. |
| AWS_ACCESS_KEY_ID | No | - | Access Key of your IAM User, make sure you've set proper permissions to [start stream transcription](https://docs.aws.amazon.com/transcribe/latest/APIReference/API_streaming_StartStreamTranscription.html). Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).  |
| AWS_SECRET_ACCESS_KEY | No | - | Secret Key of your IAM User. Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html). |