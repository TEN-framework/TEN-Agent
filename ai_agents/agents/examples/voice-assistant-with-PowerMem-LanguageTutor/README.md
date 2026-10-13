# Language Learning Companion (with PowerMem)

A voice AI language tutor enhanced with [PowerMem](https://github.com/oceanbase/powermem/) for persistent memory of vocabulary, learning progress, and personalized lessons.

## Overview

This is a **memory-enabled voice AI use case** for the Oceanbase Developer Challenge 2026. The Language Learning Companion uses TEN Framework with PowerMem to provide personalized language education that:

- **Remembers vocabulary words** learned across sessions
- **Tracks grammar concepts** covered in each lesson
- **Provides personalized practice** based on the learner's level
- **Reviews previously learned material** to reinforce memory
- **Adapts to learning style** through long-term context accumulation

## Use Case: Personalized Language Tutor

### Memory Design

The tutor uses PowerMem to store and retrieve different types of learning data:

| Memory Type | Content | Retrieval Strategy |
|-------------|---------|-------------------|
| **Vocabulary** | Words, phrases, translations | Semantic search by topic/language |
| **Grammar** | Rules, examples, explanations | Context-aware retrieval by topic |
| **Progress** | Lesson history, quiz scores | Timeline-based review |
| **Preferences** | Learning style, native language | User profile retrieval |

### How Memory Works

1. **Learning New Words**: When a user learns a new vocabulary word, it's stored with metadata (language, level, topic)
2. **Grammar Sessions**: Each grammar lesson is summarized and stored for future reference
3. **Personalized Review**: Before each session, relevant memories are retrieved to provide context
4. **Progress Tracking**: Quiz results and practice scores are saved to track improvement

### Example Conversation Flow

```
User: Teach me the Spanish word for "apple"
Tutor: "Apple" in Spanish is "manzana". Let me remember this for you.
       Now, can you use "manzana" in a sentence?

User: I eat an manzana
Tutor: Good try! The correct sentence is "Como una manzana" or "Me como una manzana".
       Remember: "manzana" is feminine (la manzana).
```

## PowerMem Configuration

Set the environment variables in `.env` file:

```bash
# Database (PowerMem/Oceanbase)
DATABASE_PROVIDER=oceanbase
OCEANBASE_HOST=127.0.0.1
OCEANBASE_PORT=2881
OCEANBASE_USER=root
OCEANBASE_PASSWORD=password
OCEANBASE_DATABASE=oceanbase
OCEANBASE_COLLECTION=language_tutor_memories

# LLM Provider (for PowerMem)
LLM_PROVIDER=qwen
LLM_API_KEY=your_qwen_api_key
LLM_MODEL=qwen-plus

# Embedding Provider (for PowerMem)
EMBEDDING_PROVIDER=qwen
EMBEDDING_API_KEY=your_qwen_api_key
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMS=1536

# Voice Services
AGORA_APP_ID=your_agora_app_id
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVENLABS_TTS_KEY=your_elevenlabs_key

# LLM for Chat
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4
```

## Prerequisites

### Required Services

1. **Oceanbase Database** (for PowerMem)
   ```bash
   docker run -d \
     --name seekdb \
     -p 2881:2881 \
     -p 2886:2886 \
     -v ./data:/var/lib/oceanbase \
     -e SEEKDB_DATABASE=powermem \
     -e ROOT_PASSWORD=password \
     oceanbase/seekdb:latest
   ```

2. **Agora Account** - Get credentials from [Agora Console](https://console.agora.io/)
   - `AGORA_APP_ID` (required)

3. **API Keys**:
   - Deepgram for ASR (`DEEPGRAM_API_KEY`)
   - ElevenLabs for TTS (`ELEVENLABS_TTS_KEY`)
   - OpenAI for LLM (`OPENAI_API_KEY`)
   - Qwen for PowerMem embeddings (`LLM_API_KEY`, `EMBEDDING_API_KEY`)

## Quick Start

1. **Install dependencies:**
   ```bash
   task install
   ```

2. **Run the Language Tutor:**
   ```bash
   task run
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - API Server: http://localhost:8080
   - TMAN Designer: http://localhost:49483

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Language Learning Companion               │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐    ┌───────────┐    ┌───────────────────┐    │
│  │  Agora    │◄──►│  STT      │◄──►│  Main Controller  │    │
│  │  RTC      │    │ (Deepgram)│    │  (with PowerMem)  │    │
│  └───────────┘    └───────────┘    └───────────────────┘    │
│                                              │               │
│  ┌───────────┐    ┌───────────┐    ┌───────▼───────┐       │
│  │  TTS      │◄──►│  LLM      │◄──►│  PowerMem     │       │
│  │(Elevenlabs)│    │ (GPT-4)  │    │  Memory Store │       │
│  └───────────┘    └───────────┘    └───────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Memory Flow

1. **Input**: User speaks via Agora RTC
2. **STT**: Audio converted to text via Deepgram
3. **Processing**: Main controller extracts learning content
4. **Memory Retrieval**: PowerMem searches for relevant memories
5. **LLM Generation**: GPT-4 generates contextual response
6. **Memory Storage**: New learning content saved to PowerMem
7. **Output**: Response spoken via ElevenLabs TTS

## Customization

### Adjust Memory Settings

Modify `tenapp/property.json`:

```json
"memory_save_interval_turns": 3,    // Save every N turns
"memory_idle_timeout_seconds": 60.0, // Session timeout
"max_memory_length": 20              // Max conversation history
```

### Customize Tutor Persona

Update the `custom_system_prompt` in `property.json`:

```json
"custom_system_prompt": "You are a Spanish tutor..."
```

## Project Structure

```
voice-assistant-with-PowerMem-LanguageTutor/
├── Dockerfile
├── README.md
├── Taskfile.yml
├── Taskfile.docker.yml
└── tenapp/
    ├── .tenignore
    ├── go.mod
    ├── go.sum
    ├── main.go
    ├── manifest.json
    ├── manifest-lock.json
    ├── property.json
    └── scripts/
        ├── install_python_deps.sh
        └── start.sh
```

## Docker Deployment

### Build Image

```bash
docker build -f Dockerfile -t language-tutor-app .
```

### Run Container

```bash
docker run --rm -it --env-file .env \
  -p 8080:8080 \
  -p 3000:3000 \
  language-tutor-app
```

## Troubleshooting

- **Memory not persisting**: Check Oceanbase connection and `OCEANBASE_*` variables
- **Audio issues**: Verify `AGORA_APP_ID`, `DEEPGRAM_API_KEY`, `ELEVENLABS_TTS_KEY`
- **LLM errors**: Confirm `OPENAI_API_KEY` is valid
- **PowerMem errors**: Ensure `LLM_API_KEY` and `EMBEDDING_API_KEY` are set

## License

MIT License - Part of TEN Framework

## References

- [TEN Framework](https://github.com/TEN-framework/ten-framework)
- [PowerMem](https://github.com/oceanbase/powermem/)
- [Oceanbase Developer Challenge 2026](https://github.com/TEN-framework/ten-framework/issues/2013)
