#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json
import time
from ten_runtime import (
    Data,
    TenEnv,
    AsyncTenEnv,
)
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_VENDOR,
)
from ten_ai_base.types import LLMToolMetadataParameter, LLMToolResultLLMResult
from ten_ai_base.llm_tool import (
    AsyncLLMToolBaseExtension,
    LLMToolMetadata,
    LLMToolResult,
)
from .config import OpenAIGPTImageConfig
from .openai_image_client import (
    OpenAIImageClient,
    ContentPolicyError,
    InvalidAPIKeyError,
    ModelNotFoundError,
)


class OpenAIGPTImageExtension(AsyncLLMToolBaseExtension):
    """
    OpenAI GPT Image 1.5 Extension

    Provides AI image generation using OpenAI's GPT Image 1.5 model
    with fallback to DALL-E 3. Integrates as an LLM tool for
    conversational image creation.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.config: OpenAIGPTImageConfig = None
        self.client: OpenAIImageClient = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        """Initialize extension with configuration and client"""
        await super().on_start(ten_env)

        # Load configuration from property.json
        ten_env.log_info("Loading OpenAI GPT Image configuration...")
        config_json_str, _ = await ten_env.get_property_to_json("")
        self.config = OpenAIGPTImageConfig.model_validate_json(config_json_str)

        # Log config (with sensitive data encrypted)
        ten_env.log_info(
            f"Configuration loaded: {self.config.to_str()}",
            category=LOG_CATEGORY_KEY_POINT,
        )

        # Validate configuration
        try:
            self.config.validate()
            self.config.update_params()
        except ValueError as e:
            ten_env.log_error(f"Configuration validation failed: {e}")
            raise

        # Initialize OpenAI client
        self.client = OpenAIImageClient(self.config, ten_env)
        ten_env.log_info(
            "OpenAI GPT Image client initialized successfully",
            category=LOG_CATEGORY_KEY_POINT,
        )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        """Cleanup resources"""
        await super().on_stop(ten_env)

        if self.client:
            await self.client.cleanup()
            ten_env.log_info("OpenAI client cleaned up")

    def get_tool_metadata(self, ten_env: TenEnv) -> list[LLMToolMetadata]:
        """Register image generation tool with LLM"""
        return [
            LLMToolMetadata(
                name="generate_image",
                description=(
                    "Generate an image from a text description using AI. "
                    "Creates high-quality, creative images based on detailed prompts. "
                    "Use this when the user asks to create, draw, make, or generate an image."
                ),
                parameters=[
                    LLMToolMetadataParameter(
                        name="prompt",
                        type="string",
                        description=(
                            "Detailed description of the image to generate. "
                            "Include style, subject, mood, colors, and composition. "
                            "Be specific and descriptive for best results. "
                            "Use the same language as the user's request."
                        ),
                        required=True,
                    ),
                    LLMToolMetadataParameter(
                        name="quality",
                        type="string",
                        description=(
                            "Image quality: 'standard' for faster generation, "
                            "'hd' for higher detail (optional, defaults to configured value)"
                        ),
                        required=False,
                    ),
                ],
            )
        ]

    async def send_image(
        self, async_ten_env: AsyncTenEnv, image_url: str
    ) -> None:
        """Send generated image URL to frontend"""
        async_ten_env.log_info(f"Sending image URL: {image_url}")

        try:
            payload_obj = {
                "data_type": "raw",
                "role": "assistant",
                "text": json.dumps(
                    {"type": "image_url", "data": {"image_url": image_url}}
                ),
                "text_ts": int(time.time() * 1000),
                "is_final": True,
                "stream_id": 100,
            }

            msg = Data.create("message")
            msg.set_property_from_json(None, json.dumps(payload_obj))
            await async_ten_env.send_data(msg)

            async_ten_env.log_info(
                "Image URL sent successfully", category=LOG_CATEGORY_KEY_POINT
            )

        except Exception as err:
            async_ten_env.log_error(
                f"Failed to send image URL: {err}", category=LOG_CATEGORY_VENDOR
            )

    async def run_tool(
        self, ten_env: AsyncTenEnv, name: str, args: dict
    ) -> LLMToolResult | None:
        """Execute image generation tool"""
        ten_env.log_info(f"run_tool {name} with args: {args}")

        if name != "generate_image":
            return None

        prompt = args.get("prompt")
        if not prompt or not prompt.strip():
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(
                    {
                        "success": False,
                        "error": "No prompt provided. Please describe what image you want to create.",
                    }
                ),
            )

        try:
            # Override quality if specified
            quality = args.get("quality", self.config.params.get("quality"))

            # Enforce kid-friendly doodle style
            unsafe_keywords = [
                "weapon",
                "blood",
                "violence",
                "gore",
                "nsfw",
                "adult",
                "gun",
                "knife",
                "kill",
                "attack",
                "war",
            ]
            lowered = prompt.lower()
            if any(k in lowered for k in unsafe_keywords):
                return LLMToolResultLLMResult(
                    type="llmresult",
                    content=json.dumps(
                        {
                            "success": False,
                            "error": "Let's try a kid-friendly idea. Describe a playful scene or character to doodle!",
                        }
                    ),
                )
            doodle_modifier = (
                " in playful crayon doodle style, hand-drawn, bold uneven outlines, "
                "simple shapes, flat colors, limited palette, minimal detail, no gradients, no 3D, "
                "no realistic lighting, no photo realism, kid-friendly and cheerful, "
                "plain white background only (no paper texture or borders), "
                "no pens, pencils, markers, hands, desks, or background props"
            )
            prompt = f"{prompt.strip()}{doodle_modifier}"

            # Emit progress: queued → drawing
            try:
                queued_msg = {
                    "data_type": "raw",
                    "role": "assistant",
                    "text": json.dumps(
                        {
                            "type": "progress",
                            "data": {"phase": "queued", "pct": 10},
                        }
                    ),
                    "text_ts": int(time.time() * 1000),
                    "is_final": False,
                    "stream_id": 100,
                }
                msg = Data.create("message")
                msg.set_property_from_json(None, json.dumps(queued_msg))
                await ten_env.send_data(msg)
            except Exception:
                pass

            # Generate image
            ten_env.log_info(
                f"Generating image with prompt: {prompt[:100]}...",
                category=LOG_CATEGORY_KEY_POINT,
            )
            try:
                generating_msg = {
                    "data_type": "raw",
                    "role": "assistant",
                    "text": json.dumps(
                        {
                            "type": "progress",
                            "data": {"phase": "drawing", "pct": 50},
                        }
                    ),
                    "text_ts": int(time.time() * 1000),
                    "is_final": False,
                    "stream_id": 100,
                }
                msg2 = Data.create("message")
                msg2.set_property_from_json(None, json.dumps(generating_msg))
                await ten_env.send_data(msg2)
            except Exception:
                pass
            image_url = await self.client.generate_image(
                prompt=prompt,
                quality=quality,
            )

            # Send image to frontend
            await self.send_image(ten_env, image_url)

            # Emit progress: final
            try:
                final_msg = {
                    "data_type": "raw",
                    "role": "assistant",
                    "text": json.dumps(
                        {
                            "type": "progress",
                            "data": {"phase": "final", "pct": 100},
                        }
                    ),
                    "text_ts": int(time.time() * 1000),
                    "is_final": True,
                    "stream_id": 100,
                }
                msg3 = Data.create("message")
                msg3.set_property_from_json(None, json.dumps(final_msg))
                await ten_env.send_data(msg3)
            except Exception:
                pass

            # Return success to LLM (without image data to avoid context overflow)
            # The image is already sent to the frontend via send_image()
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(
                    {
                        "success": True,
                        "message": "Image generated and sent to the user successfully!",
                    }
                ),
            )

        except ContentPolicyError as e:
            error_msg = (
                "I can't create that image. Let's try something different!"
            )
            ten_env.log_warn(
                f"Content policy violation: {e}", category=LOG_CATEGORY_VENDOR
            )

            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps({"success": False, "error": error_msg}),
            )

        except InvalidAPIKeyError as e:
            error_msg = "API key is invalid. Please check your configuration."
            ten_env.log_error(
                f"Invalid API key: {e}", category=LOG_CATEGORY_VENDOR
            )

            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps({"success": False, "error": error_msg}),
            )

        except ModelNotFoundError as e:
            # Try fallback model
            fallback_model = self.config.params.get("fallback_model")
            if fallback_model and fallback_model != self.client.current_model:
                ten_env.log_warn(
                    f"Model {self.client.current_model} not available, "
                    f"falling back to {fallback_model}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                try:
                    image_url = await self.client.generate_image(
                        prompt=prompt,
                        quality=quality,
                        model_override=fallback_model,
                    )
                    await self.send_image(ten_env, image_url)
                    return LLMToolResultLLMResult(
                        type="llmresult",
                        content=json.dumps(
                            {
                                "success": True,
                                "message": f"Image generated with {fallback_model} and sent to the user successfully!",
                            }
                        ),
                    )
                except Exception as fallback_error:
                    error_msg = "Image generation is temporarily unavailable."
                    ten_env.log_error(
                        f"Fallback also failed: {fallback_error}",
                        category=LOG_CATEGORY_VENDOR,
                    )
            else:
                error_msg = "Image generation model is not available."

            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps({"success": False, "error": error_msg}),
            )

        except Exception as e:
            error_msg = "Something went wrong. Please try again."
            ten_env.log_error(
                f"Image generation failed: {e}", category=LOG_CATEGORY_VENDOR
            )

            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps({"success": False, "error": error_msg}),
            )
