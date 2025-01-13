## Amazon Bedrock LLM Extension

### Configurations

You can config this extension by providing following environments:

| Env | Required | Default | Notes |
| -- | -- | -- | -- |
| AWS_REGION | No | us-east-1 | The Region of Amazon Bedrock service you want to use. |
| AWS_ACCESS_KEY_ID | No | - | Access Key of your IAM User, make sure you've set proper permissions to [invoke Bedrock models](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html) and gain [models access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) in Bedrock. Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).  |
| AWS_SECRET_ACCESS_KEY | No | - | Secret Key of your IAM User, make sure you've set proper permissions to [invoke Bedrock models](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html) and gain [models access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) in Bedrock. Will use default credentials provider if not provided. Check [document](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html). |
| AWS_BEDROCK_MODEL | No | Nova (https://docs.aws.amazon.com/nova/latest/userguide/what-is-nova.html) | Bedrock model id, check [docuement](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html#model-ids-arns).  |

## Features

- Real-time video and audio interaction similar to Gemini 2.0
- Audio recognition using TEN framework's STT plugin
- Text-to-speech conversion using TEN framework's TTS plugin
- Integration with AWS Bedrock's Nova model
- Smart input truncation logic
- Multi-language support

## Requirements
- Python 3.9+
- AWS account with Bedrock access
- TEN framework with STT and TTS plugins
- Dependencies listed in requirements.txt

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS credentials:
- Set up AWS credentials with Bedrock access
- Update the api_key in configuration

## Configuration

The extension can be configured through manifest.json properties:
- `base_uri`: Bedrock API endpoint
- `region`: AWS region for Bedrock
- `aws_access_key_id`: AWS access key ID
- `aws_secret_access_key`: AWS secret access key
- `model_id`: Bedrock Nova model ID
- `language`: Language code for STT/TTS
- See manifest.json for full configuration options

## Input Truncation Logic

The extension implements smart input truncation:

1. Duration-based truncation:
   - Automatically truncates input exceeding 30 seconds
   
2. Silence-based truncation:
   - Triggers when silence exceeds 2 seconds
   
3. Manual truncation:
   - Supports user-initiated truncation

## Architecture

1. Audio Processing:
   - Uses TEN framework's STT plugin for audio recognition
   - Buffers and processes audio in real-time
   - Provides intermediate and final transcripts

2. Nova Model Integration:
   - Combines transcribed text with video input
   - Sends to Bedrock's Nova model for processing
   - Handles responses and error conditions

3. Speech Synthesis:
   - Converts Nova model responses to speech
   - Uses TEN framework's TTS plugin
   - Synchronizes with video output

## API Usage

### Commands

1. Flush Command:
```python
cmd = Cmd.create("flush")
await ten_env.send_cmd(cmd)
```

2. User Events:
```python
# User joined
cmd = Cmd.create("on_user_joined")
await ten_env.send_cmd(cmd)

# User left
cmd = Cmd.create("on_user_left")
await ten_env.send_cmd(cmd)
```

## Contributing
1. Fork the repository
2. Create a feature branch
3. Submit a pull request