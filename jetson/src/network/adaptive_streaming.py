"""
Adaptive Video Streaming Module

Adjusts video quality based on network conditions to optimize bandwidth usage.
Validates: Requirements 9.7
"""

import time
import logging
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
from collections import deque
import numpy as np


logger = logging.getLogger(__name__)


class VideoQuality(Enum):
    """Video quality presets"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


@dataclass
class QualityProfile:
    """Video quality profile parameters"""
    name: VideoQuality
    width: int
    height: int
    fps: int
    jpeg_quality: int  # 1-100
    estimated_bitrate: int  # kbps


# Predefined quality profiles
QUALITY_PROFILES = {
    VideoQuality.LOW: QualityProfile(
        name=VideoQuality.LOW,
        width=640,
        height=480,
        fps=10,
        jpeg_quality=50,
        estimated_bitrate=500
    ),
    VideoQuality.MEDIUM: QualityProfile(
        name=VideoQuality.MEDIUM,
        width=1280,
        height=720,
        fps=15,
        jpeg_quality=70,
        estimated_bitrate=1500
    ),
    VideoQuality.HIGH: QualityProfile(
        name=VideoQuality.HIGH,
        width=1280,
        height=720,
        fps=25,
        jpeg_quality=85,
        estimated_bitrate=3000
    ),
    VideoQuality.ULTRA: QualityProfile(
        name=VideoQuality.ULTRA,
        width=1920,
        height=1080,
        fps=30,
        jpeg_quality=95,
        estimated_bitrate=5000
    ),
}


@dataclass
class NetworkMetrics:
    """Network performance metrics"""
    bandwidth: float  # kbps
    latency: float  # ms
    packet_loss: float  # percentage
    jitter: float  # ms
    timestamp: float


@dataclass
class StreamingStats:
    """Streaming statistics"""
    current_quality: VideoQuality
    frames_sent: int = 0
    bytes_sent: int = 0
    quality_changes: int = 0
    average_bitrate: float = 0.0  # kbps
    dropped_frames: int = 0


class AdaptiveStreaming:
    """Adaptive video streaming manager"""
    
    def __init__(self, initial_quality: VideoQuality = VideoQuality.MEDIUM):
        """
        Initialize adaptive streaming
        
        Args:
            initial_quality: Initial video quality
        """
        self.current_quality = initial_quality
        self.current_profile = QUALITY_PROFILES[initial_quality]
        
        self.stats = StreamingStats(current_quality=initial_quality)
        
        # Network monitoring
        self._network_metrics: deque = deque(maxlen=10)  # Keep last 10 measurements
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Adaptation parameters
        self.adaptation_interval = 5.0  # seconds
        self.bandwidth_safety_margin = 0.8  # Use 80% of available bandwidth
        
        # Quality change callback
        self._quality_callback: Optional[Callable[[VideoQuality, QualityProfile], None]] = None
        
        # Frame timing for bitrate calculation
        self._frame_times: deque = deque(maxlen=30)
        self._frame_sizes: deque = deque(maxlen=30)
    
    def set_quality_callback(self, callback: Callable[[VideoQuality, QualityProfile], None]):
        """Set callback for quality changes"""
        self._quality_callback = callback
    
    def start_monitoring(self):
        """Start network monitoring and adaptation"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Monitoring already running")
            return
        
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Adaptive streaming monitoring started")
    
    def stop_monitoring(self):
        """Stop network monitoring"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Adaptive streaming monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while not self._stop_event.is_set():
            try:
                # Measure network conditions
                metrics = self._measure_network()
                if metrics:
                    self._network_metrics.append(metrics)
                
                # Adapt quality based on metrics
                if len(self._network_metrics) >= 3:  # Need at least 3 samples
                    self._adapt_quality()
                
                # Wait before next measurement
                self._stop_event.wait(self.adaptation_interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(5)
    
    def _measure_network(self) -> Optional[NetworkMetrics]:
        """
        Measure current network conditions
        
        Returns:
            Network metrics if measurement successful
        """
        try:
            # Calculate actual bitrate from recent frames
            if len(self._frame_times) >= 2 and len(self._frame_sizes) >= 2:
                time_span = self._frame_times[-1] - self._frame_times[0]
                if time_span > 0:
                    total_bytes = sum(self._frame_sizes)
                    bitrate = (total_bytes * 8) / (time_span * 1000)  # kbps
                else:
                    bitrate = 0
            else:
                bitrate = self.current_profile.estimated_bitrate
            
            # Estimate latency (simplified - in production, use ping or RTT measurements)
            latency = 50.0  # ms, placeholder
            
            # Packet loss and jitter would be measured from actual network stats
            packet_loss = 0.0
            jitter = 5.0
            
            metrics = NetworkMetrics(
                bandwidth=bitrate,
                latency=latency,
                packet_loss=packet_loss,
                jitter=jitter,
                timestamp=time.time()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Network measurement error: {e}")
            return None
    
    def _adapt_quality(self):
        """Adapt video quality based on network conditions"""
        try:
            # Calculate average metrics
            avg_bandwidth = np.mean([m.bandwidth for m in self._network_metrics])
            avg_latency = np.mean([m.latency for m in self._network_metrics])
            avg_packet_loss = np.mean([m.packet_loss for m in self._network_metrics])
            
            logger.debug(f"Network: {avg_bandwidth:.0f} kbps, {avg_latency:.0f} ms latency, {avg_packet_loss:.1f}% loss")
            
            # Determine target quality based on available bandwidth
            available_bandwidth = avg_bandwidth * self.bandwidth_safety_margin
            
            target_quality = self._select_quality(available_bandwidth, avg_latency, avg_packet_loss)
            
            if target_quality != self.current_quality:
                self._change_quality(target_quality)
            
        except Exception as e:
            logger.error(f"Quality adaptation error: {e}")
    
    def _select_quality(self, bandwidth: float, latency: float, packet_loss: float) -> VideoQuality:
        """
        Select appropriate quality based on network conditions
        
        Args:
            bandwidth: Available bandwidth in kbps
            latency: Network latency in ms
            packet_loss: Packet loss percentage
            
        Returns:
            Recommended video quality
        """
        # Penalize for high latency or packet loss
        if latency > 200 or packet_loss > 5:
            bandwidth *= 0.7
        elif latency > 100 or packet_loss > 2:
            bandwidth *= 0.85
        
        # Select quality that fits within bandwidth
        if bandwidth >= QUALITY_PROFILES[VideoQuality.ULTRA].estimated_bitrate:
            return VideoQuality.ULTRA
        elif bandwidth >= QUALITY_PROFILES[VideoQuality.HIGH].estimated_bitrate:
            return VideoQuality.HIGH
        elif bandwidth >= QUALITY_PROFILES[VideoQuality.MEDIUM].estimated_bitrate:
            return VideoQuality.MEDIUM
        else:
            return VideoQuality.LOW
    
    def _change_quality(self, new_quality: VideoQuality):
        """Change video quality"""
        try:
            old_quality = self.current_quality
            self.current_quality = new_quality
            self.current_profile = QUALITY_PROFILES[new_quality]
            
            self.stats.current_quality = new_quality
            self.stats.quality_changes += 1
            
            logger.info(f"Quality changed: {old_quality.value} -> {new_quality.value}")
            
            # Notify callback
            if self._quality_callback:
                try:
                    self._quality_callback(new_quality, self.current_profile)
                except Exception as e:
                    logger.error(f"Quality callback error: {e}")
            
        except Exception as e:
            logger.error(f"Quality change error: {e}")
    
    def record_frame(self, frame_size: int):
        """
        Record frame transmission for bitrate calculation
        
        Args:
            frame_size: Frame size in bytes
        """
        now = time.time()
        self._frame_times.append(now)
        self._frame_sizes.append(frame_size)
        
        self.stats.frames_sent += 1
        self.stats.bytes_sent += frame_size
        
        # Update average bitrate
        if len(self._frame_times) >= 2:
            time_span = self._frame_times[-1] - self._frame_times[0]
            if time_span > 0:
                total_bytes = sum(self._frame_sizes)
                self.stats.average_bitrate = (total_bytes * 8) / (time_span * 1000)
    
    def get_current_profile(self) -> QualityProfile:
        """Get current quality profile"""
        return self.current_profile
    
    def set_quality(self, quality: VideoQuality):
        """
        Manually set video quality
        
        Args:
            quality: Desired video quality
        """
        if quality != self.current_quality:
            self._change_quality(quality)
    
    def get_stats(self) -> StreamingStats:
        """Get streaming statistics"""
        return self.stats
    
    def reset_stats(self):
        """Reset streaming statistics"""
        self.stats = StreamingStats(current_quality=self.current_quality)
        self._frame_times.clear()
        self._frame_sizes.clear()


class BandwidthEstimator:
    """Estimate available bandwidth"""
    
    def __init__(self, window_size: int = 10):
        """
        Initialize bandwidth estimator
        
        Args:
            window_size: Number of samples to keep for averaging
        """
        self.window_size = window_size
        self._samples: deque = deque(maxlen=window_size)
    
    def add_sample(self, bytes_sent: int, duration: float):
        """
        Add bandwidth sample
        
        Args:
            bytes_sent: Number of bytes sent
            duration: Time duration in seconds
        """
        if duration > 0:
            bitrate = (bytes_sent * 8) / (duration * 1000)  # kbps
            self._samples.append(bitrate)
    
    def get_estimate(self) -> float:
        """
        Get bandwidth estimate
        
        Returns:
            Estimated bandwidth in kbps
        """
        if not self._samples:
            return 0.0
        
        # Use exponential weighted moving average
        weights = np.exp(np.linspace(-1, 0, len(self._samples)))
        weights /= weights.sum()
        
        return np.average(list(self._samples), weights=weights)
    
    def get_percentile(self, percentile: float = 10) -> float:
        """
        Get bandwidth percentile (useful for conservative estimates)
        
        Args:
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Bandwidth at given percentile in kbps
        """
        if not self._samples:
            return 0.0
        
        return np.percentile(list(self._samples), percentile)
