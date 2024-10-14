#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import json

from typing import Any
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from .log import logger

PROPERTY_KEY = "key"
PROPERTY_ENDPOINT = "endpoint"

CMD_IMAGE_ANALYZE = "image_analyze"

class AzureVisionExtension(Extension):
    key: str = ""
    endpoint: str = "https://tenagentvision.cognitiveservices.azure.com/"

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("AzureVisionExtension on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("AzureVisionExtension on_start")

        try:
            self.key = ten_env.get_property_string(PROPERTY_KEY)
        except Exception as err:
            logger.error(f"GetProperty optional {PROPERTY_KEY} error: {err}")
            return
        
        try:
            self.endpoint = ten_env.get_property_string(PROPERTY_ENDPOINT)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_ENDPOINT} error: {err}")

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("AzureVisionExtension on_stop")
        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("AzureVisionExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd name {}".format(cmd_name))

        if cmd_name == CMD_IMAGE_ANALYZE:
            try:
                image_data = cmd.get_property_buf("image_data")
                resp = self._analyze_image(image_data)
                cmd_result = CmdResult.create(StatusCode.OK)
                cmd_result.set_property_string("response", json.dumps(resp))
                ten_env.return_result(cmd_result, cmd)
                return
            except:
                logger.exception("Failed to handle analyze")

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass

    def _analyze_image(self, image_data: bytes) -> Any:
        client = ImageAnalysisClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )

        # Get a caption for the image. This will be a synchronously (blocking) call.
        result = client.analyze(
            image_data=image_data,
            visual_features=[VisualFeatures.TAGS, VisualFeatures.CAPTION, VisualFeatures.READ, VisualFeatures.PEOPLE, VisualFeatures.OBJECTS],
            gender_neutral_caption=True,
        )

        logger.info(f"before return {result}")

        rst = {}
        if result.tags is not None:
            tags = []
            for tag in result.tags.list:
                tags.append({
                    "name": tag.name,
                    "confidence": tag.confidence
                })
            rst["tags"] = tags

        if result.caption is not None:
            rst["caption"] = {
                "text": result.caption.text,
                "confidence": result.caption.confidence
            }

        if result.read is not None:
            lines = []
            for block in result.read.blocks:
                for line in block.lines:
                    lines.append({
                        "text": line.text,
                        "bounding_box": str(line.bounding_polygon),
                    })
            rst["read"] = lines

        if result.objects is not None:
            objects = []
            for object in result.objects.list:
                objects.append({
                    "name": object.tags[0].name,
                    "bounding_box": str(object.bounding_box),
                    "confidence": object.tags[0].confidence
                })
            rst["objects"] = objects

        if result.people is not None:
            people = []
            for person in result.people.list:
                people.append({
                    "bounding_box": str(person.bounding_box),
                    "confidence": person.confidence
                })
            rst["people"] = people
        
        logger.info(f"after parse {rst}")

        return rst