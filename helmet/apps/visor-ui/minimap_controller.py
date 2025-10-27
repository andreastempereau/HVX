#!/usr/bin/env python3
"""Minimap controller for GPS visualization with map tiles"""

import logging
import math
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple
from PySide6.QtCore import QObject, Signal, QTimer, Slot
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QTransform
from PySide6.QtQuick import QQuickImageProvider
import threading

logger = logging.getLogger(__name__)

def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """Convert lat/lon to tile coordinates at given zoom level"""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)

def tile_to_lat_lon(x: int, y: int, zoom: int) -> Tuple[float, float]:
    """Convert tile coordinates to lat/lon"""
    n = 2.0 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return (lat, lon)

class MinimapImageProvider(QQuickImageProvider):
    """Image provider for minimap rendering"""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self.current_image = QImage()
        self.lock = threading.Lock()

    def requestImage(self, id, size, requestedSize):
        """Provide image to QML"""
        with self.lock:
            if not self.current_image.isNull():
                return self.current_image.copy()
            else:
                # Return empty circular minimap if no data
                empty = QImage(300, 300, QImage.Format_ARGB32)
                empty.fill(QColor(40, 40, 40, 200))
                return empty

    def setImage(self, image: QImage):
        """Update the current image"""
        with self.lock:
            self.current_image = image

class MinimapController(QObject):
    """Controller for minimap with GPS and map tiles"""

    # Signals
    minimapUpdated = Signal(str)  # Signal to refresh minimap
    statusUpdated = Signal('QVariantMap')

    def __init__(self, image_provider: MinimapImageProvider, cache_dir: str = ".map_cache"):
        super().__init__()
        self.image_provider = image_provider

        # Map settings
        self.zoom_level = 17  # Good zoom for street-level detail
        self.minimap_size = 300  # Size in pixels
        self.tile_size = 256  # Standard tile size

        # Position and orientation
        self.latitude: Optional[float] = None
        self.longitude: Optional[float] = None
        self.heading: float = 0.0  # Heading from IMU (0-360 degrees)

        # Tile cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tile_cache = {}  # In-memory cache

        # Update counter
        self.update_counter = 0

        # Use OpenStreetMap tiles
        self.tile_server = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        self.user_agent = "HelmetHUD/1.0"

    def update_position(self, lat: float, lon: float):
        """Update GPS position"""
        self.latitude = lat
        self.longitude = lon
        self._render_minimap()

    def update_heading(self, heading: float):
        """Update heading from IMU (0-360 degrees)"""
        self.heading = heading
        self._render_minimap()

    def set_zoom(self, zoom: int):
        """Set zoom level (0-19, where 19 is most zoomed in)"""
        self.zoom_level = max(0, min(19, zoom))
        self._render_minimap()

    def _get_tile(self, x: int, y: int, zoom: int) -> Optional[QImage]:
        """Get tile from cache or download"""
        cache_key = f"{zoom}_{x}_{y}"

        # Check in-memory cache
        if cache_key in self.tile_cache:
            return self.tile_cache[cache_key]

        # Check disk cache
        cache_file = self.cache_dir / f"{cache_key}.png"
        if cache_file.exists():
            image = QImage(str(cache_file))
            if not image.isNull():
                self.tile_cache[cache_key] = image
                return image

        # Download tile in background (don't block UI)
        # For now, return a placeholder
        return self._get_placeholder_tile()

    def _download_tile_async(self, x: int, y: int, zoom: int):
        """Download tile asynchronously"""
        def download():
            try:
                cache_key = f"{zoom}_{x}_{y}"
                cache_file = self.cache_dir / f"{cache_key}.png"

                # Build URL
                url = self.tile_server.format(z=zoom, x=x, y=y)

                # Download
                req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = response.read()

                # Save to cache
                cache_file.write_bytes(data)

                # Load into memory
                image = QImage()
                image.loadFromData(data)
                if not image.isNull():
                    self.tile_cache[cache_key] = image
                    # Trigger re-render
                    self._render_minimap()

            except Exception as e:
                logger.debug(f"Failed to download tile {x},{y} at zoom {zoom}: {e}")

        thread = threading.Thread(target=download, daemon=True)
        thread.start()

    def _get_placeholder_tile(self) -> QImage:
        """Get placeholder tile when real tile is not available"""
        tile = QImage(self.tile_size, self.tile_size, QImage.Format_RGB888)
        tile.fill(QColor(60, 60, 60))

        # Draw grid
        painter = QPainter(tile)
        painter.setPen(QColor(80, 80, 80))
        for i in range(0, self.tile_size, 32):
            painter.drawLine(i, 0, i, self.tile_size)
            painter.drawLine(0, i, self.tile_size, i)
        painter.end()

        return tile

    def _render_minimap(self):
        """Render the minimap"""
        if self.latitude is None or self.longitude is None:
            # No GPS position yet, render placeholder
            self._render_no_gps()
            return

        try:
            # Create minimap image
            minimap = QImage(self.minimap_size, self.minimap_size, QImage.Format_ARGB32)
            minimap.fill(QColor(0, 0, 0, 0))  # Transparent

            painter = QPainter(minimap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            # Get center tile
            center_tile_x, center_tile_y = lat_lon_to_tile(self.latitude, self.longitude, self.zoom_level)

            # Calculate how many tiles we need to cover the minimap
            tiles_needed = math.ceil(self.minimap_size / self.tile_size) + 1

            # Download tiles in background if not cached
            for dx in range(-tiles_needed, tiles_needed + 1):
                for dy in range(-tiles_needed, tiles_needed + 1):
                    tile_x = center_tile_x + dx
                    tile_y = center_tile_y + dy
                    cache_key = f"{self.zoom_level}_{tile_x}_{tile_y}"
                    if cache_key not in self.tile_cache:
                        self._download_tile_async(tile_x, tile_y, self.zoom_level)

            # Calculate pixel offset within center tile
            n = 2.0 ** self.zoom_level
            world_x = (self.longitude + 180.0) / 360.0 * n * self.tile_size
            lat_rad = math.radians(self.latitude)
            world_y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * self.tile_size

            # Offset from tile origin
            offset_x = world_x - (center_tile_x * self.tile_size)
            offset_y = world_y - (center_tile_y * self.tile_size)

            # Apply rotation based on heading (disabled if heading is 0)
            if self.heading != 0:
                center = self.minimap_size / 2
                painter.translate(center, center)
                painter.rotate(-self.heading)  # Negative to rotate map, not player
                painter.translate(-center, -center)

            # Draw tiles
            for dx in range(-tiles_needed, tiles_needed + 1):
                for dy in range(-tiles_needed, tiles_needed + 1):
                    tile_x = center_tile_x + dx
                    tile_y = center_tile_y + dy

                    tile_image = self._get_tile(tile_x, tile_y, self.zoom_level)
                    if tile_image:
                        # Calculate position
                        pos_x = center + (dx * self.tile_size) - offset_x
                        pos_y = center + (dy * self.tile_size) - offset_y

                        painter.drawImage(int(pos_x), int(pos_y), tile_image)

            # Reset transform for player marker
            painter.resetTransform()

            # Draw player marker (center of minimap)
            self._draw_player_marker(painter, center, center)

            # Draw circular mask (make it look like a circular minimap)
            self._apply_circular_mask(painter, center)

            painter.end()

            # Update image provider
            self.image_provider.setImage(minimap)
            self.update_counter += 1
            self.minimapUpdated.emit(f"image://minimap/{self.update_counter}")

        except Exception as e:
            logger.error(f"Minimap render error: {e}")
            self._render_no_gps()

    def _draw_player_marker(self, painter: QPainter, x: float, y: float):
        """Draw player marker at center"""
        # Draw direction indicator (triangle pointing up = north)
        painter.save()
        painter.translate(x, y)
        painter.rotate(0)  # Already oriented by map rotation

        # Draw player dot
        painter.setBrush(QColor(0, 150, 255, 220))
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawEllipse(-8, -8, 16, 16)

        # Draw direction arrow
        painter.setBrush(QColor(255, 200, 0, 255))
        painter.setPen(QColor(255, 255, 255, 255))
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        arrow = QPolygonF([
            QPointF(0, -12),
            QPointF(-6, 4),
            QPointF(0, 0),
            QPointF(6, 4)
        ])
        painter.drawPolygon(arrow)

        painter.restore()

    def _apply_circular_mask(self, painter: QPainter, center: float):
        """Apply circular mask to make minimap round"""
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)

        # Create circular gradient (fade at edges)
        from PySide6.QtGui import QRadialGradient
        gradient = QRadialGradient(center, center, center)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 255))
        gradient.setColorAt(0.85, QColor(255, 255, 255, 255))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setBrush(gradient)
        painter.setPen(QColor(0, 0, 0, 0))
        painter.drawEllipse(0, 0, self.minimap_size, self.minimap_size)

        # Draw border
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.setPen(QColor(200, 200, 200, 200))
        painter.drawEllipse(2, 2, self.minimap_size - 4, self.minimap_size - 4)

    def _render_no_gps(self):
        """Render placeholder when no GPS signal"""
        minimap = QImage(self.minimap_size, self.minimap_size, QImage.Format_ARGB32)
        minimap.fill(QColor(40, 40, 40, 200))

        painter = QPainter(minimap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circular border
        painter.setPen(QColor(100, 100, 100, 200))
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawEllipse(2, 2, self.minimap_size - 4, self.minimap_size - 4)

        # Draw "NO GPS" text
        painter.setPen(QColor(200, 200, 200, 200))
        from PySide6.QtGui import QFont
        from PySide6.QtCore import Qt, QRectF
        font = QFont("Arial", 16, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, self.minimap_size, self.minimap_size),
                        Qt.AlignCenter, "NO GPS")

        painter.end()

        self.image_provider.setImage(minimap)
        self.update_counter += 1
        self.minimapUpdated.emit(f"image://minimap/{self.update_counter}")

    @Slot(int)
    def adjustZoom(self, delta: int):
        """Adjust zoom level"""
        self.set_zoom(self.zoom_level + delta)
