"""Video service gRPC client"""

import grpc
import logging
from typing import Optional

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "libs"))
from messages import helmet_pb2, helmet_pb2_grpc

logger = logging.getLogger(__name__)

class VideoClient:
    """Client for video service communication"""

    def __init__(self, server_address: str):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self._connect()

    def _connect(self):
        """Connect to video service"""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = helmet_pb2_grpc.VideoServiceStub(self.channel)

            # Test connection
            request = helmet_pb2.FrameRequest()
            request.source = "default"
            response = self.stub.GetFrame(request, timeout=5)

            logger.info(f"Connected to video service at {self.server_address}")

        except Exception as e:
            logger.error(f"Failed to connect to video service: {e}")
            raise

    def get_frame(self) -> Optional[helmet_pb2.FrameMeta]:
        """Get a single frame from video service"""
        try:
            if not self.stub:
                return None

            request = helmet_pb2.FrameRequest()
            request.source = "default"

            response = self.stub.GetFrame(request, timeout=1)
            return response

        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                logger.error(f"Video service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting frame: {e}")
            return None

    def stream_frames(self):
        """Stream frames from video service"""
        try:
            if not self.stub:
                return

            request = helmet_pb2.FrameRequest()
            request.source = "default"

            for frame_meta in self.stub.StreamFrames(request):
                yield frame_meta

        except grpc.RpcError as e:
            logger.error(f"Video stream error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in frame stream: {e}")

    def disconnect(self):
        """Disconnect from video service"""
        if self.channel:
            self.channel.close()
            logger.info("Disconnected from video service")