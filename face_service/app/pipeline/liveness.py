"""
Enhanced Liveness Detection with multi-signal anti-spoofing.

Detects presentation attacks (photos, screens, video replay) using:
- Two-frame movement analysis (original)
- LBP texture analysis (printed photo detection)
- FFT moiré pattern detection (screen detection)
- Glare/highlight analysis (glossy surface detection)
- Color distribution analysis (unnatural patterns)
- Temporal uniformity (video replay detection)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings
from app.pipeline.detector import FaceDetector

logger = logging.getLogger(__name__)


@dataclass
class LivenessScores:
    """Component scores from each anti-spoofing check."""
    movement: float = 0.0
    eye_movement: float = 0.0
    texture: float = 0.0
    moire: float = 0.0
    glare: float = 0.0
    color_variance: float = 0.0
    temporal_uniformity: float = 0.0


@dataclass
class LivenessResult:
    """Result of liveness detection check with detailed scoring."""
    is_live: bool
    confidence: float
    reason: str
    scores: LivenessScores = field(default_factory=LivenessScores)


class LivenessDetector:
    """
    Enhanced liveness detector with multi-signal anti-spoofing.
    
    Combines movement analysis with texture, frequency, and color
    analysis to detect various presentation attacks.
    """
    
    def __init__(self):
        self.detector = FaceDetector()
        self.movement_threshold = settings.LIVENESS_MOVEMENT_THRESHOLD
    
    def check_liveness(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray
    ) -> LivenessResult:
        """
        Check if the face is from a live person using multiple signals.
        
        Combines temporal movement analysis with static image analysis
        to detect photos, screens, and video replay attacks.
        """
        faces1 = self.detector.detect(frame1)
        faces2 = self.detector.detect(frame2)
        
        if not faces1:
            return LivenessResult(
                is_live=False,
                confidence=0.0,
                reason="No face detected in first frame"
            )
        
        if not faces2:
            return LivenessResult(
                is_live=False,
                confidence=0.0,
                reason="No face detected in second frame"
            )
        
        face1 = faces1[0]
        face2 = faces2[0]
        
        scores = LivenessScores()
        
        movement = self._calculate_movement(face1.landmarks, face2.landmarks)
        scores.movement = movement
        
        if movement < 0.001:
            return LivenessResult(
                is_live=False,
                confidence=0.1,
                reason="No movement detected - possible photo attack",
                scores=scores
            )
        
        if movement > 0.15:
            return LivenessResult(
                is_live=False,
                confidence=0.2,
                reason="Excessive movement - please hold still",
                scores=scores
            )
        
        scores.eye_movement = self._check_eye_movement(face1.landmarks, face2.landmarks)
        
        face_crop1 = self._extract_face_crop(frame1, face1.bbox)
        face_crop2 = self._extract_face_crop(frame2, face2.bbox)
        
        if face_crop1 is None or face_crop2 is None:
            return LivenessResult(
                is_live=False,
                confidence=0.0,
                reason="Could not extract face region"
            )
        
        scores.texture = self._analyze_texture(face_crop1)
        scores.moire = self._detect_moire(face_crop1)
        scores.glare = self._detect_glare(face_crop1)
        scores.color_variance = self._analyze_color_distribution(face_crop1)
        scores.temporal_uniformity = self._check_temporal_uniformity(face_crop1, face_crop2)
        
        confidence, reason, attack_type = self._fuse_scores(scores)
        
        is_live = confidence >= settings.LIVENESS_CONFIDENCE_THRESHOLD
        
        if not is_live and attack_type:
            reason = f"Possible {attack_type} attack detected"
        elif is_live:
            reason = "Natural patterns detected - live face verified"
        
        logger.debug(
            f"Liveness check: is_live={is_live}, confidence={confidence:.3f}, "
            f"movement={scores.movement:.4f}, texture={scores.texture:.3f}, "
            f"moire={scores.moire:.3f}, glare={scores.glare:.3f}"
        )
        
        return LivenessResult(
            is_live=is_live,
            confidence=confidence,
            reason=reason,
            scores=scores
        )
    
    def _extract_face_crop(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int]
    ) -> Optional[np.ndarray]:
        """Extract face region with padding for analysis."""
        x1, y1, x2, y2 = bbox
        h, w = image.shape[:2]
        
        pad_x = int((x2 - x1) * 0.2)
        pad_y = int((y2 - y1) * 0.2)
        
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)
        
        crop = image[y1:y2, x1:x2]
        
        if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
            return None
        
        return crop
    
    def _calculate_movement(
        self,
        landmarks1: np.ndarray,
        landmarks2: np.ndarray
    ) -> float:
        """Calculate normalized movement between landmark sets."""
        displacement = np.linalg.norm(landmarks2 - landmarks1, axis=1)
        eye_distance = np.linalg.norm(landmarks1[0] - landmarks1[1])
        
        if eye_distance < 1:
            return 0.0
        
        normalized = displacement / eye_distance
        return float(np.mean(normalized))
    
    def _check_eye_movement(
        self,
        landmarks1: np.ndarray,
        landmarks2: np.ndarray
    ) -> float:
        """Check for eye region movement (potential blink)."""
        left_eye_diff = abs(landmarks2[0, 1] - landmarks1[0, 1])
        right_eye_diff = abs(landmarks2[1, 1] - landmarks1[1, 1])
        return float((left_eye_diff + right_eye_diff) / 2)
    
    def _analyze_texture(self, face_crop: np.ndarray) -> float:
        """
        Analyze skin texture using Local Binary Patterns (LBP).
        
        Real faces have rich, varied micro-texture from skin pores.
        Printed photos and screens show uniform or pixelated texture.
        Returns score in [0,1] where 1 = natural texture.
        """
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        
        if gray.shape[0] > 128:
            scale = 128 / gray.shape[0]
            gray = cv2.resize(gray, None, fx=scale, fy=scale)
        
        lbp = self._compute_lbp(gray)
        
        hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
        hist = hist.astype(float) / (hist.sum() + 1e-7)
        
        entropy = -np.sum(hist * np.log2(hist + 1e-10))
        variance = np.var(lbp)
        
        entropy_score = min(1.0, entropy / 7.0)
        variance_score = min(1.0, variance / 2000.0)
        
        texture_score = 0.6 * entropy_score + 0.4 * variance_score
        
        return float(np.clip(texture_score, 0.0, 1.0))
    
    def _compute_lbp(self, gray: np.ndarray, radius: int = 1) -> np.ndarray:
        """Compute Local Binary Pattern descriptor."""
        padded = np.pad(gray, radius, mode='edge')
        lbp = np.zeros_like(gray, dtype=np.uint8)
        
        neighbors = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, 1), (1, 1), (1, 0),
            (1, -1), (0, -1)
        ]
        
        center = padded[radius:-radius, radius:-radius]
        
        for i, (dy, dx) in enumerate(neighbors):
            neighbor = padded[radius + dy:padded.shape[0] - radius + dy,
                             radius + dx:padded.shape[1] - radius + dx]
            lbp |= ((neighbor >= center).astype(np.uint8) << i)
        
        return lbp
    
    def _detect_moire(self, face_crop: np.ndarray) -> float:
        """
        Detect moiré patterns using FFT high-frequency analysis.
        
        Screens display characteristic periodic patterns from pixel grids.
        Returns score in [0,1] where 1 = no moiré (likely real).
        """
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128))
        
        f_transform = np.fft.fft2(gray.astype(np.float32))
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)
        
        magnitude = np.log1p(magnitude)
        
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        
        y, x = np.ogrid[:h, :w]
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        
        low_freq_mask = dist <= (min(h, w) * 0.1)
        mid_freq_mask = (dist > (min(h, w) * 0.1)) & (dist <= (min(h, w) * 0.35))
        high_freq_mask = dist > (min(h, w) * 0.35)
        
        low_energy = np.sum(magnitude[low_freq_mask])
        mid_energy = np.sum(magnitude[mid_freq_mask])
        high_energy = np.sum(magnitude[high_freq_mask])
        total_energy = low_energy + mid_energy + high_energy + 1e-7
        
        high_ratio = high_energy / total_energy
        
        if high_ratio > settings.LIVENESS_MOIRE_THRESHOLD:
            return max(0.0, 1.0 - (high_ratio - settings.LIVENESS_MOIRE_THRESHOLD) * 3)
        
        return 1.0
    
    def _detect_glare(self, face_crop: np.ndarray) -> float:
        """
        Detect specular reflections/glare from screens or glossy photos.
        
        Returns score in [0,1] where 1 = no glare (likely real).
        """
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        
        high_value = hsv[:, :, 2] > 240
        low_saturation = hsv[:, :, 1] < 30
        glare_mask = high_value & low_saturation
        
        glare_ratio = np.sum(glare_mask) / (glare_mask.size + 1e-7)
        
        if glare_ratio > settings.LIVENESS_GLARE_THRESHOLD:
            return max(0.0, 1.0 - (glare_ratio - settings.LIVENESS_GLARE_THRESHOLD) * 5)
        
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        bright_spots = gray > 250
        bright_ratio = np.sum(bright_spots) / (bright_spots.size + 1e-7)
        
        if bright_ratio > 0.1:
            return max(0.3, 1.0 - bright_ratio * 3)
        
        return 1.0
    
    def _analyze_color_distribution(self, face_crop: np.ndarray) -> float:
        """
        Analyze color distribution for natural skin tones.
        
        Real faces show gradual color transitions and varied hues.
        Printed photos may show banding or limited color gamut.
        Returns score in [0,1] where 1 = natural distribution.
        """
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        
        hue_std = np.std(hsv[:, :, 0])
        sat_std = np.std(hsv[:, :, 1])
        val_std = np.std(hsv[:, :, 2])
        
        color_variance = (hue_std + sat_std + val_std) / 3.0
        
        normalized_variance = min(1.0, color_variance / 50.0)
        
        if normalized_variance < settings.LIVENESS_COLOR_VARIANCE_MIN:
            return float(normalized_variance / settings.LIVENESS_COLOR_VARIANCE_MIN * 0.5)
        
        lab = cv2.cvtColor(face_crop, cv2.COLOR_BGR2LAB)
        a_channel = lab[:, :, 1].astype(float)
        b_channel = lab[:, :, 2].astype(float)
        
        a_range = np.percentile(a_channel, 95) - np.percentile(a_channel, 5)
        b_range = np.percentile(b_channel, 95) - np.percentile(b_channel, 5)
        
        chromatic_score = min(1.0, (a_range + b_range) / 60.0)
        
        return float(np.clip(0.5 * normalized_variance + 0.5 * chromatic_score, 0.0, 1.0))
    
    def _check_temporal_uniformity(
        self,
        crop1: np.ndarray,
        crop2: np.ndarray
    ) -> float:
        """
        Check for unnatural temporal uniformity (video replay detection).
        
        Video replays often show very uniform frame-to-frame changes.
        Real faces have natural micro-variation in lighting/expression.
        Returns score in [0,1] where 1 = natural variation.
        """
        size = (64, 64)
        gray1 = cv2.cvtColor(cv2.resize(crop1, size), cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(cv2.resize(crop2, size), cv2.COLOR_BGR2GRAY)
        
        diff = cv2.absdiff(gray1, gray2).astype(float)
        
        mean_diff = np.mean(diff)
        std_diff = np.std(diff)
        
        if mean_diff < 0.5:
            return 0.3
        
        coefficient_of_variation = std_diff / (mean_diff + 1e-7)
        
        if coefficient_of_variation < 0.3:
            uniformity = 1.0 - coefficient_of_variation / 0.3
            if uniformity > settings.LIVENESS_TEMPORAL_UNIFORMITY_MAX:
                return max(0.2, 1.0 - uniformity)
        
        natural_variation_score = min(1.0, coefficient_of_variation / 1.0)
        
        return float(np.clip(natural_variation_score, 0.0, 1.0))
    
    def _fuse_scores(
        self,
        scores: LivenessScores
    ) -> Tuple[float, str, Optional[str]]:
        """
        Fuse all component scores into final confidence with attack detection.
        
        Uses weighted combination with penalty for suspicious signals.
        """
        movement_score = self._movement_to_score(scores.movement)
        eye_bonus = min(scores.eye_movement * 8, 0.15)
        
        weights = {
            'movement': 0.25,
            'texture': 0.20,
            'moire': 0.15,
            'glare': 0.15,
            'color': 0.15,
            'temporal': 0.10
        }
        
        weighted_sum = (
            weights['movement'] * movement_score +
            weights['texture'] * scores.texture +
            weights['moire'] * scores.moire +
            weights['glare'] * scores.glare +
            weights['color'] * scores.color_variance +
            weights['temporal'] * scores.temporal_uniformity
        )
        
        confidence = weighted_sum + eye_bonus
        
        attack_type = None
        reason = "Analyzing liveness signals"
        
        if scores.texture < settings.LIVENESS_TEXTURE_THRESHOLD:
            confidence *= 0.7
            attack_type = "printed photo"
            reason = "Unnatural texture pattern detected"
        
        if scores.moire < 0.5:
            confidence *= 0.7
            attack_type = attack_type or "screen display"
            reason = "Screen moiré pattern detected"
        
        if scores.glare < 0.5:
            confidence *= 0.8
            attack_type = attack_type or "glossy surface"
            reason = "Specular reflection detected"
        
        if scores.temporal_uniformity < 0.4:
            confidence *= 0.75
            attack_type = attack_type or "video replay"
            reason = "Unnatural temporal uniformity"
        
        confidence = float(np.clip(confidence, 0.0, 1.0))
        
        return confidence, reason, attack_type
    
    def _movement_to_score(self, movement: float) -> float:
        """Convert movement value to liveness score."""
        if 0.005 <= movement <= 0.08:
            deviation = abs(movement - 0.03) / 0.05
            return max(0.0, 1.0 - deviation)
        elif movement > 0.08:
            return max(0.0, 0.5 - (movement - 0.08) / 0.14)
        else:
            return float(movement / 0.005 * 0.3)
