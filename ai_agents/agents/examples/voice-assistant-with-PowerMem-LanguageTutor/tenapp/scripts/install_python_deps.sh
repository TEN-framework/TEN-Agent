#!/bin/bash
# Install Python dependencies for Language Tutor with PowerMem

# Install main extension dependencies
echo "Installing main Python dependencies..."
cd ../../ten_packages/extension/main_python
pip install -r requirements.txt -q

# Install openai_llm2_python dependencies
echo "Installing LLM extension dependencies..."
cd ../../ten_packages/extension/openai_llm2_python
pip install -r requirements.txt -q

echo "Python dependencies installed successfully."
