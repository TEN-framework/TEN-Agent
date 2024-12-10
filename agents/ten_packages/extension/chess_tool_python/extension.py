import json
import requests
import chess
import chess.engine

from typing import Any

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

CMD_TOOL_REGISTER = "tool_register"
CMD_TOOL_CALL = "tool_call"
CMD_PROPERTY_NAME = "name"
CMD_PROPERTY_ARGS = "args"

TOOL_REGISTER_PROPERTY_NAME = "name"
TOOL_REGISTER_PROPERTY_DESCRIPTON = "description"
TOOL_REGISTER_PROPERTY_PARAMETERS = "parameters"
TOOL_CALLBACK = "callback"

DRAW_TOOL_NAME = "draw_chessboard"
DRAW_TOOL_DESCRIPTION = (
    "Use this function to show the chessboard in the additional content window and to draw or update all the piece positions on it. Call this function after each player makes his move, do not forget. "    
)
DRAW_TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "current_forsyth": {
            "type": "string",
            "description": "The Forsyth string representing all the current chess piece positions, or Forsyth = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR' to indicate the standard starting position for all pieces.",
        }
    },
    "required": ["current_forsyth"],
}

VALIDATE_TOOL_NAME = "validate_chess_move"
VALIDATE_TOOL_DESCRIPTION = "Validate a user's suggested move before allowing it."
VALIDATE_TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "current_forsyth": {
            "type": "string",
            "description": "The Forsyth string representing all the current chess piece positions, or Forsyth = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR' to indicate the standard starting position for all pieces.",
        },
        "move": {
            "type": "string",
            "description": "The proposed move in UCI format (e.g., 'e2e4').",
        },
    },
    "required": ["current_forsyth", "move"],
}

MOVE_TOOL_NAME = "suggest_next_chess_move"
MOVE_TOOL_DESCRIPTION = "Suggest the best next move to make and the new Forsyth following the move. Always call this function to find your next move."
MOVE_TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "current_forsyth": {
            "type": "string",
            "description": "The Forsyth string representing all the current chess piece positions, or Forsyth = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR' to indicate the standard starting position for all pieces.",
        }
    },
    "required": ["current_forsyth"],
}

PROPERTY_API_KEY = "api_key"  # Required

class ChessToolExtension(Extension):
    api_key: str = ""
    tools: dict = {}
    ten_env: Any = None

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("ChessToolExtension on_init")
        self.ten_env = ten_env
        self.tools = {
            DRAW_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: DRAW_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: DRAW_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: DRAW_TOOL_PARAMETERS,
                TOOL_CALLBACK: self._draw_chessboard,
            },
            VALIDATE_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: VALIDATE_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: VALIDATE_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: VALIDATE_TOOL_PARAMETERS,
                TOOL_CALLBACK: self._validate_chess_move,
            },
            MOVE_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: MOVE_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: MOVE_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: MOVE_TOOL_PARAMETERS,
                TOOL_CALLBACK: self._suggest_next_chess_move,
            },
        }

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("ChessToolExtension on_start")

        try:
            api_key = ten_env.get_property_string(PROPERTY_API_KEY)
            self.api_key = api_key
        except Exception as err:
            logger.info(f"GetProperty required {PROPERTY_API_KEY} failed, err: {err}")
            return

        # Register tools
        for name, tool in self.tools.items():
            c = Cmd.create(CMD_TOOL_REGISTER)
            c.set_property_string(TOOL_REGISTER_PROPERTY_NAME, name)
            c.set_property_string(
                TOOL_REGISTER_PROPERTY_DESCRIPTON, tool[TOOL_REGISTER_PROPERTY_DESCRIPTON]
            )
            c.set_property_string(
                TOOL_REGISTER_PROPERTY_PARAMETERS,
                json.dumps(tool[TOOL_REGISTER_PROPERTY_PARAMETERS]),
            )
            ten_env.send_cmd(
                c, lambda ten, result: logger.info(f"register done, {result}")
            )

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("ChessToolExtension on_stop")
        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("ChessToolExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info(f"on_cmd name {cmd_name} {cmd.to_json()}")

        try:
            name = cmd.get_property_string(CMD_PROPERTY_NAME)
            if name in self.tools:
                tool = self.tools[name]
                args = cmd.get_property_string(CMD_PROPERTY_ARGS)
                arg_dict = json.loads(args)
                logger.info(f"before callback {name}")
                resp = tool[TOOL_CALLBACK](arg_dict)
                logger.info(f"after callback {resp}")
                cmd_result = CmdResult.create(StatusCode.OK)
                cmd_result.set_property_string("response", json.dumps(resp))
                ten_env.return_result(cmd_result, cmd)
                return
            else:
                logger.error(f"unknown tool name {name}")
        except Exception as e:
            logger.exception("Failed to process command")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            ten_env.return_result(cmd_result, cmd)
            return

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass

    def _draw_chessboard(self, args: dict) -> Any:
        forsyth = args["current_forsyth"]
        logger.info(f"_draw_chessboard with Forsyth: {forsyth}")
        try:
            d = Data.create("text_data")
            d.set_property_string("text", f"SSML_CHESSBOARD {forsyth}")
            d.set_property_bool("end_of_segment", True)
            d.set_property_int("stream_id", 0)
            d.set_property_bool("is_final", True)
            self.ten_env.send_data(d)
            logger.info(f"SSML_CHESSBOARD {d}")
        except Exception:
            logger.exception("Error sending SSML")
        return "SUCCESS"

    def _validate_chess_move(self, args: dict) -> Any:
        current_forsyth = args["current_forsyth"]
        move_uci = args["move"]
        logger.info(f"Validating move {move_uci} on Forsyth: {current_forsyth}")
        try:
            # Handle 'start' as a special case
            if current_forsyth =="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR":
                board = chess.Board()  # Standard starting position
            else:
                board = chess.Board(current_forsyth)
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                return {"valid": True, "message": "Move is valid."}
            else:
                return {"valid": False, "message": "Move is invalid."}
        except Exception as e:
            logger.exception("Error validating move")
            return {"valid": False, "message": f"Error: {str(e)}"}


    def _suggest_next_chess_move(self, args: dict) -> Any:
        # apt update
        # apt-get install stockfish

        forsyth = args["current_forsyth"]
        logger.info(f"Suggesting next move for Forsyth: {forsyth}")
        try:
            if forsyth == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR":
                board = chess.Board()  # Standard starting position
            else:
                board = chess.Board(forsyth)
            engine = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
            limit = chess.engine.Limit(time=0.1)  # Adjust time as needed
            result = engine.play(board, limit)
            suggested_move = result.move
            board.push(suggested_move)  # Apply the move to the board
            new_forsyth = board.forsyth()       # Get the updated Forsyth
            engine.quit()
            logger.info(f"Suggested move: {suggested_move.uci()}")
            return {"suggested_move": suggested_move.uci(), "forsyth_after_move": new_forsyth}
        except Exception as e:
            logger.exception("Error suggesting next move")
            return {"error": f"Error: {str(e)}"}