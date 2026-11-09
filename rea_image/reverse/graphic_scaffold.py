"""Vector SVG scaffold generator for graphic design, posters, banners, and infographics."""

from typing import List, Optional
from rea_image.schemas import PaletteColor, RegionAnalysis


class GraphicScaffoldBuilder:
    """Generates layered SVG files reproducing image layout, geometry, and palette."""

    def build_svg(
        self,
        width: int,
        height: int,
        palette: List[PaletteColor],
        regions: Optional[List[RegionAnalysis]] = None,
    ) -> str:
        bg_color = palette[0].hex if palette else "#FFFFFF"
        accent_color = next((p.hex for p in palette if p.role == "accent"), "#0066CC")
        text_color = next((p.hex for p in palette if p.role == "text"), "#111111")

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
            '  <defs>',
            '    <linearGradient id="primaryGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
            f'      <stop offset="0%" stop-color="{bg_color}" />',
            f'      <stop offset="100%" stop-color="{accent_color}" stop-opacity="0.8" />',
            '    </linearGradient>',
            '    <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">',
            '      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-opacity="0.15" />',
            '    </filter>',
            '  </defs>',
            '  <!-- Background Layer -->',
            f'  <rect width="{width}" height="{height}" fill="{bg_color}" />',
        ]

        # Draw region blocks
        if regions:
            for r in regions:
                x, y, w, h = r.bbox
                if r.label == "background":
                    continue
                elif r.label == "text_block":
                    svg_lines.append(f'  <!-- Text Block: {r.id} -->')
                    svg_lines.append(f'  <g id="{r.id}" transform="translate({x}, {y})">')
                    svg_lines.append(f'    <text x="0" y="{min(h, 36)}" font-family="system-ui, -apple-system, sans-serif" font-size="{min(h, 32)}" font-weight="bold" fill="{text_color}">Headline Text</text>')
                    svg_lines.append('  </g>')
                else:
                    svg_lines.append(f'  <!-- Graphic Layer: {r.id} ({r.label}) -->')
                    svg_lines.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{accent_color}" filter="url(#cardShadow)" opacity="0.9" />')
        else:
            # Default placeholder graphic card
            card_w = int(width * 0.7)
            card_h = int(height * 0.5)
            card_x = (width - card_w) // 2
            card_y = (height - card_h) // 2
            svg_lines.append(f'  <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" fill="url(#primaryGrad)" filter="url(#cardShadow)" />')
            svg_lines.append(f'  <text x="{width // 2}" y="{height // 2}" font-family="system-ui, sans-serif" font-size="28" font-weight="600" fill="{text_color}" text-anchor="middle">Vector Graphic Scaffold</text>')

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)

