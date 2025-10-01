"""Perception service gRPC client"""

import grpc
import logging
from typing import Optional

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "libs"))
from messages import helmet_pb2, helmet_pb2_grpc

logger = logging.getLogger(__name__)

class PerceptionClient:
    """Client for perception service communication"""

    def __init__(self, server_address: str):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self._connect()

    def _connect(self):
        """Connect to perception service"""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = helmet_pb2_grpc.PerceptionServiceStub(self.channel)
            logger.info(f"Connected to perception service at {self.server_address}")

        except Exception as e:
            logger.error(f"Failed to connect to perception service: {e}")
            raise

    def infer(self, frame_meta: helmet_pb2.FrameMeta) -> Optional[helmet_pb2.DetectionResult]:
        """Run inference on a frame"""
        try:
            if not self.stub:
                return None

            response = self.stub.Infer(frame_meta, timeout=2)
            return response

        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                logger.error(f"Perception service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during inference: {e}")
            return None

    def set_roi(self, x: float, y: float, width: float, height: float, enabled: bool = True) -> bool:
        """Set region of interest for detection"""
        try:
            if not self.stub:
                return False

            request = helmet_pb2.ROIRequest()
            request.x = x
            request.y = y
            request.width = width
            request.height = height
            request.enabled = enabled

            response = self.stub.SetROI(request, timeout=1)
            return response.success

        except Exception as e:
            logger.error(f"Error setting ROI: {e}")
            return False

    def disconnect(self):
        """Disconnect from perception service"""
        if self.channel:
            self.channel.close()
            logger.info("Disconnected from perception service")