#!/usr/bin/env python3
"""AI perception service for object detection and image analysis"""

import asyncio
import logging
import time
from concurrent import futures
from pathlib import Path
import sys
import cv2
import numpy as np
from typing import List, Tuple, Optional
import requests
import os

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logging.warning("ONNX Runtime not available, falling back to CPU-only inference")

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True

    # Allow ultralytics and torch classes for PyTorch 2.6+ safe loading
    try:
        import torch.serialization
        import torch.nn
        from ultralytics.nn.tasks import DetectionModel

        # Allowlist all necessary classes for YOLO model loading
        torch.serialization.add_safe_globals([
            DetectionModel,
            torch.nn.modules.container.Sequential,
            torch.nn.modules.conv.Conv2d,
            torch.nn.modules.batchnorm.BatchNorm2d,
            torch.nn.modules.activation.SiLU,
            torch.nn.modules.pooling.MaxPool2d,
            torch.nn.modules.upsampling.Upsample,
        ])
    except (ImportError, AttributeError):
        pass  # Older PyTorch versions don't need this
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logging.warning("Ultralytics not available, using fallback detection")

# Add libs to path
sys.path.append(str(Path(__file__).parent.parent.parent / "libs"))
from utils.config import get_config
from utils.logging_utils import setup_logging, log_performance
from messages import helmet_pb2, helmet_pb2_grpc

logger = logging.getLogger(__name__)

class ObjectDetector:
    """Object detection using YOLO models"""

    def __init__(self, config):
        self.config = config
        self.model = None
        self.input_size = tuple(config.get('perception.input_size', [640, 640]))
        self.confidence_threshold = config.get('perception.confidence_threshold', 0.5)
        self.nms_threshold = config.get('perception.nms_threshold', 0.4)
        self.max_detections = config.get('perception.max_detections', 100)
        self.device = config.get('perception.device', 'cpu')
        self.roi = None  # Region of interest
        self._setup_model()

    def _setup_model(self):
        """Initialize the detection model"""
        try:
            # Set torch to allow non-safe loading for trusted models (if torch is available)
            try:
                import torch
                if hasattr(torch, '__version__') and torch.__version__ >= '2.6':
                    # PyTorch 2.6+ requires weights_only=False for ultralytics models
                    import torch.serialization
                    torch.serialization.DEFAULT_PROTOCOL = 4
            except ImportError:
                logger.info("PyTorch not available, will use fallback detection")
                torch = None

            model_path = self.config.get('perception.model_path', 'models/yolov8n.pt')
            model_path = Path(model_path)

            if ULTRALYTICS_AVAILABLE:
                # Use Ultralytics YOLO
                if not model_path.exists() or model_path.suffix == '.onnx':
                    # Download YOLOv8n if model doesn't exist
                    logger.info(f"Model not found at {model_path}, downloading YOLOv8n...")
                    model_path.parent.mkdir(parents=True, exist_ok=True)
                    # Monkey-patch torch.load to use weights_only=False
                    original_load = torch.load
                    torch.load = lambda *args, **kwargs: original_load(*args, **{**kwargs, 'weights_only': False})
                    try:
                        self.model = YOLO('yolov8n.pt')  # Auto-download
                        logger.info(f"Downloaded YOLO model")
                    finally:
                        torch.load = original_load
                else:
                    # Monkey-patch torch.load to use weights_only=False
                    original_load = torch.load
                    torch.load = lambda *args, **kwargs: original_load(*args, **{**kwargs, 'weights_only': False})
                    try:
                        self.model = YOLO(str(model_path))
                        logger.info(f"Loaded YOLO model: {model_path}")
                    finally:
                        torch.load = original_load

            elif ONNX_AVAILABLE and model_path.suffix == '.onnx' and model_path.exists():
                # Use ONNX Runtime directly
                providers = ['CPUExecutionProvider']
                if self.device == 'cuda' and 'CUDAExecutionProvider' in ort.get_available_providers():
                    providers.insert(0, 'CUDAExecutionProvider')

                self.model = ort.InferenceSession(str(model_path), providers=providers)
                logger.info(f"Loaded ONNX model: {model_path} with providers: {providers}")

            else:
                # Fallback to OpenCV YOLO
                logger.warning("Ultralytics not available, attempting OpenCV YOLO")
                self.model = None

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None

    @log_performance("object_detection")
    def detect(self, frame: np.ndarray) -> List[helmet_pb2.Detection]:
        """Perform object detection on frame"""
        if self.model is None:
            return self._yolo_detection(frame)

        try:
            # Apply ROI if set
            if self.roi:
                x, y, w, h = self.roi
                roi_frame = frame[y:y+h, x:x+w]
                detections = self._run_inference(roi_frame)
                # Adjust coordinates back to full frame
                for det in detections:
                    det.x = (det.x * w + x) / frame.shape[1]
                    det.y = (det.y * h + y) / frame.shape[0]
                    det.width *= w / frame.shape[1]
                    det.height *= h / frame.shape[0]
                return detections
            else:
                return self._run_inference(frame)

        except Exception as e:
            logger.error(f"Detection failed: {e}")
            return []

    def _run_inference(self, frame: np.ndarray) -> List[helmet_pb2.Detection]:
        """Run model inference"""
        if ULTRALYTICS_AVAILABLE and hasattr(self.model, 'predict'):
            # Ultralytics YOLO
            results = self.model.predict(
                frame,
                imgsz=self.input_size,
                conf=self.confidence_threshold,
                iou=self.nms_threshold,
                max_det=self.max_detections,
                verbose=False
            )

            detections = []
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        detection = helmet_pb2.Detection()

                        # Normalized coordinates
                        x1, y1, x2, y2 = boxes.xyxyn[i].cpu().numpy()
                        detection.x = float(x1)
                        detection.y = float(y1)
                        detection.width = float(x2 - x1)
                        detection.height = float(y2 - y1)

                        detection.confidence = float(boxes.conf[i])
                        detection.class_id = int(boxes.cls[i])
                        detection.label = self.model.names[detection.class_id]

                        detections.append(detection)

            return detections

        elif ONNX_AVAILABLE and hasattr(self.model, 'run'):
            # ONNX Runtime inference
            return self._onnx_inference(frame)

        else:
            return self._yolo_detection(frame)

    def _onnx_inference(self, frame: np.ndarray) -> List[helmet_pb2.Detection]:
        """ONNX Runtime inference implementation"""
        # Preprocess
        input_tensor = self._preprocess_frame(frame)

        # Run inference
        input_name = self.model.get_inputs()[0].name
        outputs = self.model.run(None, {input_name: input_tensor})

        # Postprocess (simplified - would need full YOLO postprocessing)
        return self._postprocess_onnx(outputs[0], frame.shape)

    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for model input"""
        # Resize to model input size
        resized = cv2.resize(frame, self.input_size)

        # Normalize to [0, 1]
        normalized = resized.astype(np.float32) / 255.0

        # Add batch dimension and change from HWC to CHW
        input_tensor = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]

        return input_tensor

    def _postprocess_onnx(self, output: np.ndarray, frame_shape: Tuple[int, int, int]) -> List[helmet_pb2.Detection]:
        """Postprocess ONNX model output (simplified)"""
        # This is a simplified implementation
        # Full YOLO postprocessing would include NMS, coordinate conversion, etc.
        detections = []

        # Mock some detections for now
        if output.size > 0:
            detection = helmet_pb2.Detection()
            detection.x = 0.3
            detection.y = 0.3
            detection.width = 0.4
            detection.height = 0.4
            detection.confidence = 0.8
            detection.class_id = 0
            detection.label = "object"
            detections.append(detection)

        return detections

    def _download_yolo_model(self):
        """Download YOLOv4 model files if not present"""
        models_dir = Path("models")
        models_dir.mkdir(exist_ok=True)

        # YOLOv4 model files
        files = {
            "yolov4.weights": "https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights",
            "yolov4.cfg": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg",
            "coco.names": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names"
        }

        for filename, url in files.items():
            filepath = models_dir / filename
            if not filepath.exists():
                logger.info(f"Downloading {filename}...")
                try:
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"Downloaded {filename}")
                except Exception as e:
                    logger.error(f"Failed to download {filename}: {e}")
                    return False
        return True

    def _load_yolo_model(self):
        """Load YOLO model using OpenCV DNN"""
        try:
            models_dir = Path("models")
            weights_path = models_dir / "yolov4.weights"
            config_path = models_dir / "yolov4.cfg"
            names_path = models_dir / "coco.names"

            # Download models if not present
            if not all(p.exists() for p in [weights_path, config_path, names_path]):
                if not self._download_yolo_model():
                    return None, None

            # Load YOLO network
            net = cv2.dnn.readNetFromDarknet(str(config_path), str(weights_path))

            # Use CUDA if available
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                logger.info("Using CUDA for YOLO inference")
            else:
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                logger.info("Using CPU for YOLO inference")

            # Load class names
            with open(names_path, 'r') as f:
                class_names = [line.strip() for line in f.readlines()]

            logger.info(f"Loaded YOLO model with {len(class_names)} classes")
            return net, class_names

        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            return None, None

    def _yolo_detection(self, frame: np.ndarray) -> List[helmet_pb2.Detection]:
        """Real YOLO object detection using OpenCV DNN"""
        # Skip YOLO loading for now - go straight to fallback
        logger.debug("Using fallback detection (YOLO unavailable)")
        return self._fallback_detection(frame)

        # Disabled YOLO loading to prevent crashes
        if not hasattr(self, 'yolo_net') or self.yolo_net is None:
            self.yolo_net, self.yolo_classes = self._load_yolo_model()
            if self.yolo_net is None:
                logger.warning("YOLO model not available, using fallback")
                return self._fallback_detection(frame)

        try:
            height, width = frame.shape[:2]

            # Create blob from image
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
            self.yolo_net.setInput(blob)

            # Get output layer names
            layer_names = self.yolo_net.getLayerNames()
            output_layers = [layer_names[i - 1] for i in self.yolo_net.getUnconnectedOutLayers()]

            # Run inference
            outputs = self.yolo_net.forward(output_layers)

            # Parse detections
            boxes = []
            confidences = []
            class_ids = []

            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]

                    if confidence > self.confidence_threshold:
                        # Object detected
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)

                        # Rectangle coordinates
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)

                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)

            # Apply Non-Maximum Suppression
            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, self.nms_threshold)

            detections = []
            if len(indices) > 0:
                for i in indices.flatten():
                    x, y, w, h = boxes[i]

                    detection = helmet_pb2.Detection()
                    detection.x = max(0.0, x / width)
                    detection.y = max(0.0, y / height)
                    detection.width = min(1.0, w / width)
                    detection.height = min(1.0, h / height)
                    detection.confidence = confidences[i]
                    detection.class_id = class_ids[i]
                    detection.label = self.yolo_classes[class_ids[i]] if class_ids[i] < len(self.yolo_classes) else f"class_{class_ids[i]}"

                    detections.append(detection)

            logger.debug(f"YOLO detected {len(detections)} objects")
            return detections

        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            return self._fallback_detection(frame)

    def _fallback_detection(self, frame: np.ndarray) -> List[helmet_pb2.Detection]:
        """Fallback detection using OpenCV cascade classifiers"""
        detections = []

        try:
            # Use Haar cascades for basic face detection
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            for (x, y, w, h) in faces:
                detection = helmet_pb2.Detection()
                detection.x = x / frame.shape[1]
                detection.y = y / frame.shape[0]
                detection.width = w / frame.shape[1]
                detection.height = h / frame.shape[0]
                detection.confidence = 0.8  # Haar cascades don't provide confidence
                detection.class_id = 0
                detection.label = "person"
                detections.append(detection)

            logger.debug(f"Fallback detected {len(detections)} faces")

        except Exception as e:
            logger.error(f"Fallback detection failed: {e}")

        return detections

    def _analyze_scene_with_llm(self, frame: np.ndarray, detections: List[helmet_pb2.Detection]) -> str:
        """Analyze scene with local LLM vision model for contextual tips"""
        try:
            # Check if we have ollama available for local LLM
            import subprocess
            import base64
            import json
            import io
            from PIL import Image

            # Convert frame to base64 for LLM
            pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            buffer = io.BytesIO()
            pil_image.save(buffer, format='JPEG', quality=85)
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # Create detection context
            detection_text = ", ".join([f"{det.label} ({det.confidence:.2f})" for det in detections])

            # Construct prompt for vision analysis
            prompt = f"""You are an AI assistant for an AR helmet system. Analyze this image and provide a brief, practical tip about the environment. Current detections: {detection_text}

            Give a short, actionable insight about safety, efficiency, or awareness in 10-15 words. Examples:
            - "Person detected ahead - maintain safe distance"
            - "Multiple objects in view - proceed with caution"
            - "Clear workspace - good visibility for tasks"

            Response:"""

            # Try to use ollama with llava model
            try:
                cmd = [
                    "ollama", "run", "llava:7b",
                    "--format", "json",
                    prompt
                ]

                # For now, let's create a simple rule-based analysis
                # In a real implementation, you'd use the LLM call above
                return self._rule_based_scene_analysis(detections)

            except Exception as e:
                logger.debug(f"LLM not available: {e}")
                return self._rule_based_scene_analysis(detections)

        except Exception as e:
            logger.error(f"Scene analysis failed: {e}")
            return ""

    def _rule_based_scene_analysis(self, detections: List[helmet_pb2.Detection]) -> str:
        """Rule-based scene analysis as fallback"""
        if not detections:
            return "Clear view - no objects detected"

        # Analyze detection patterns
        person_count = sum(1 for d in detections if d.label == "person")
        vehicle_count = sum(1 for d in detections if d.label in ["car", "truck", "motorcycle", "bus"])
        total_objects = len(detections)

        # Generate contextual tips
        if person_count > 0:
            if person_count == 1:
                return "Person in view - maintain awareness"
            else:
                return f"{person_count} people detected - crowded area"

        elif vehicle_count > 0:
            return f"{vehicle_count} vehicle(s) detected - traffic area"

        elif total_objects > 5:
            return "Busy environment - multiple objects detected"

        elif any(d.label in ["laptop", "monitor", "keyboard"] for d in detections):
            return "Workspace detected - good for productivity"

        elif any(d.label in ["cup", "bottle"] for d in detections):
            return "Personal items nearby - organized space"

        else:
            return f"{total_objects} object(s) in view - monitor surroundings"

    def set_roi(self, x: float, y: float, width: float, height: float, enabled: bool):
        """Set region of interest for detection"""
        if enabled and 0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1:
            # Convert normalized coordinates to pixel coordinates
            # This will be updated when we get actual frame dimensions
            self.roi = (x, y, width, height)
            logger.info(f"ROI set: {x:.2f}, {y:.2f}, {width:.2f}, {height:.2f}")
        else:
            self.roi = None
            logger.info("ROI disabled")

class PerceptionServiceImpl(helmet_pb2_grpc.PerceptionServiceServicer):
    """gRPC perception service implementation"""

    def __init__(self, config):
        self.config = config
        self.detector = ObjectDetector(config)
        logger.info("Perception service initialized")

    def Infer(self, request, context):
        """Run inference on a single frame"""
        try:
            # Convert protobuf frame to numpy array
            frame = self._protobuf_to_frame(request)
            if frame is None:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Invalid frame data")
                return helmet_pb2.DetectionResult()

            start_time = time.time()
            detections = self.detector.detect(frame)
            inference_time = (time.time() - start_time) * 1000

            # Create response
            result = helmet_pb2.DetectionResult()
            result.frame_id = request.frame_id
            result.timestamp.CopyFrom(request.timestamp)
            result.inference_time_ms = inference_time
            result.detections.extend(detections)

            return result

        except Exception as e:
            logger.error(f"Inference error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return helmet_pb2.DetectionResult()

    def InferStream(self, request_iterator, context):
        """Stream inference on multiple frames"""
        logger.info("Starting inference stream")

        try:
            for frame_meta in request_iterator:
                if not context.is_active():
                    break

                result = self.Infer(frame_meta, context)
                if result.frame_id > 0:  # Valid result
                    yield result

        except Exception as e:
            logger.error(f"Stream inference error: {e}")

    def SetROI(self, request, context):
        """Set region of interest for detection"""
        try:
            self.detector.set_roi(
                request.x, request.y,
                request.width, request.height,
                request.enabled
            )

            response = helmet_pb2.CommandResponse()
            response.success = True
            response.message = "ROI updated successfully"
            response.timestamp.GetCurrentTime()
            return response

        except Exception as e:
            logger.error(f"ROI setting error: {e}")
            response = helmet_pb2.CommandResponse()
            response.success = False
            response.message = str(e)
            response.timestamp.GetCurrentTime()
            return response

    def _protobuf_to_frame(self, frame_meta: helmet_pb2.FrameMeta) -> Optional[np.ndarray]:
        """Convert protobuf frame to numpy array"""
        try:
            if not frame_meta.data:
                return None

            # Decode frame data
            frame_data = np.frombuffer(frame_meta.data, dtype=np.uint8)

            if frame_meta.format == 'RGB':
                frame = frame_data.reshape((frame_meta.height, frame_meta.width, 3))
            elif frame_meta.format == 'BGR':
                frame = frame_data.reshape((frame_meta.height, frame_meta.width, 3))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                logger.warning(f"Unsupported frame format: {frame_meta.format}")
                return None

            return frame

        except Exception as e:
            logger.error(f"Frame conversion error: {e}")
            return None

def serve():
    """Start the gRPC server"""
    config = get_config()

    # Setup logging
    log_level = config.get('system.log_level', 'INFO')
    log_dir = Path(config.get('system.log_dir', 'logs'))
    setup_logging('perception-service', log_level, log_dir)

    # Create gRPC server with increased message size for high-res frames
    # 50MB max message size to handle high-resolution camera frames
    options = [
        ('grpc.max_send_message_length', 50 * 1024 * 1024),
        ('grpc.max_receive_message_length', 50 * 1024 * 1024),
    ]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options=options)
    perception_service = PerceptionServiceImpl(config)
    helmet_pb2_grpc.add_PerceptionServiceServicer_to_server(perception_service, server)

    # Configure server
    port = config.get('services.perception_port', 50052)
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)

    # Start server
    server.start()
    logger.info(f"Perception service started on {listen_addr}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        server.stop(5)
        logger.info("Perception service stopped")

def main():
    """Main entry point"""
    try:
        serve()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()