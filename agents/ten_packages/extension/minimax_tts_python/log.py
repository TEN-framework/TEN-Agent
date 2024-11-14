#
#
# Agora Real Time Engagement
# Created by Tomas Liu/XinHui Li in 2024.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import logging

logger = logging.getLogger("minimax_tts_python")
logger.setLevel(logging.INFO)

formatter_str = ("%(asctime)s - %(name)s - %(levelname)s - %(process)d - [%(filename)s:%(lineno)d] - %(message)s")
formatter = logging.Formatter(formatter_str)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)
