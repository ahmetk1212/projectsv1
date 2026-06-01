"""
Object Detection — OpenCV DNN with YOLOv4-tiny
Lightweight enough for Raspberry Pi 3A+.
Falls back to a simple motion/difference detector if weights unavailable.
"""
import os
import logging
import time
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ObjectDetector:
    """
    Object detection using OpenCV DNN + YOLOv4-tiny.
    Provides per-frame bounding boxes and labels.
    Falls back gracefully when model files are not present.
    """

    def __init__(self, config: dict):
        self.cfg = config
        self.enabled = config.get('DETECTION_ENABLED', True)
        self.confidence = config.get('DETECTION_CONFIDENCE', 0.45)
        self.nms_thresh = config.get('DETECTION_NMS', 0.45)
        self.classes = config.get('DETECTION_CLASSES', [])
        self.model_dir = config.get('MODEL_DIR', '/workspace/models')

        self._net = None
        self._layer_names = None
        self._use_fallback = False

        if self.enabled:
            self._init_model()

    def _init_model(self):
        """Try to load YOLOv4-tiny from disk."""
        weights = os.path.join(self.model_dir, self.cfg.get('DETECTION_WEIGHTS', 'yolov4-tiny.weights'))
        cfg = os.path.join(self.model_dir, self.cfg.get('DETECTION_CFG', 'yolov4-tiny.cfg'))

        if os.path.exists(weights) and os.path.exists(cfg):
            try:
                self._net = cv2.dnn.readNet(str(weights), str(cfg))
                # Use GPU if available, otherwise CPU
                try:
                    self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                    self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                    logger.info("Detection: using CUDA GPU")
                except Exception:
                    self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                    self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                    logger.info("Detection: using CPU")

                self._layer_names = self._net.getLayerNames()
                self._output_layers = [
                    self._layer_names[i - 1]
                    for i in self._net.getUnconnectedOutLayers()
                ]
                logger.info(f"Detection: YOLOv4-tiny loaded from {weights}")
                return
            except Exception as e:
                logger.warning(f"Failed to load YOLOv4-tiny: {e}")

        logger.info("Detection: using FALLBACK (simple motion/difference detection)")
        self._use_fallback = True

    def _get_fallback_detection(self, frame: np.ndarray, prev_frame: Optional[np.ndarray]) -> List[dict]:
        """
        Simple fallback: background subtraction + contour detection.
        Works without any model weights.
        """
        detections = []
        if prev_frame is None:
            return detections

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)

        diff = cv2.absdiff(prev_gray, gray)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = (frame.shape[1] * frame.shape[0]) * 0.005  # 0.5% of frame

        for cnt in contours:
            if cv2.contourArea(cnt) < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            # Estimate label based on size
            area_ratio = cv2.contourArea(cnt) / min_area
            if area_ratio > 10:
                label = "large_object"
            elif area_ratio > 4:
                label = "person"
            else:
                label = "movement"
            detections.append({
                'label': label,
                'confidence': min(0.95, 0.4 + area_ratio * 0.05),
                'bbox': (x, y, w, h)
            })

        return detections

    def detect(self, frame: np.ndarray, prev_frame: Optional[np.ndarray] = None) -> List[dict]:
        """
        Run detection on a frame.
        Returns list of detections with label, confidence, bbox.
        """
        if not self.enabled:
            return []

        if self._use_fallback:
            return self._get_fallback_detection(frame, prev_frame)

        # YOLOv4-tiny inference
        blob = cv2.dnn.blobFromImage(
            frame, 1 / 255.0, (416, 416), swapRB=True, crop=False
        )
        self._net.setInput(blob)
        outputs = self._net.forward(self._output_layers)

        h, w = frame.shape[:2]
        detections = []
        boxes, confidences, class_ids = [], [], []

        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = float(scores[class_id])
                if confidence < self.confidence:
                    continue

                cx, cy, bw, bh = detection[0:4] * np.array([w, h, w, h])
                x = int(cx - bw / 2)
                y = int(cy - bh / 2)
                w2 = int(bw)
                h2 = int(bh)

                boxes.append([x, y, w2, h2])
                confidences.append(confidence)
                class_ids.append(class_id)

        # Non-Maximum Suppression
        if boxes:
            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence, self.nms_thresh)
            for idx in indices:
                i = idx if isinstance(idx, (int, np.integer)) else int(idx)
                if i >= len(boxes):
                    continue
                x, y, bw, bh = boxes[i]
                label = self.classes[class_ids[i]] if class_ids[i] < len(self.classes) else 'object'
                detections.append({
                    'label': label,
                    'confidence': confidences[i],
                    'bbox': (x, y, bw, bh)
                })

        return detections

    def toggle(self):
        self.enabled = not self.enabled
        logger.info(f"Detection {'enabled' if self.enabled else 'disabled'}")
        return self.enabled