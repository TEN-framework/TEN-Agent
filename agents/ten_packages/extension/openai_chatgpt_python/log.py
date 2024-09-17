#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import logging
import colorlog

# Create logger
logger = logging.getLogger("openai_chatgpt_python")
logger.setLevel(logging.INFO)

# Define log format with colors
formatter_str = (
    "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(process)d - "
    "[%(filename)s:%(lineno)d] - %(message)s"
)
formatter = logging.Formatter(formatter_str)

# Create a colored formatter
formatter = colorlog.ColoredFormatter(
    formatter_str,
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
)

# Create console handler and set the colored formatter
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Add handler to the logger
logger.addHandler(console_handler)