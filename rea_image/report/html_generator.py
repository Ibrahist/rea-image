"""Self-contained interactive HTML report generator."""

from pathlib import Path
from jinja2 import Template
from rea_image.schemas import ReportSchema


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>rea-image Report — {{ report.image.path.split('/')[-1].split('\\\\')[-1] }}</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: var(--font);
      line-height: 1.5;
      padding: 32px 24px;
    }
    .container { max-width: 1200px; margin: 0 auto; }
    header { margin-bottom: 32px; border-bottom: 1px solid var(--border); padding-bottom: 24px; }
    h1 { font-size: 2rem; font-weight: 800; color: #fff; margin-bottom: 8px; }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .badge-high { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
    .badge-medium { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
    .badge-low { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
    .verdict-banner {
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      border: 1px solid var(--accent);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 32px;
    }
    .verdict-title { font-size: 1.4rem; font-weight: 700; color: var(--accent); margin-bottom: 8px; }
    .verdict-summary { font-size: 1.1rem; color: #fff; }
    .breakdown-bar {
      display: flex;
      height: 12px;
      border-radius: 6px;
      overflow: hidden;
      margin-top: 16px;
      background: #334155;
    }
    .breakdown-seg { height: 100%; transition: width 0.3s; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }
    @media (max-width: 860px) { .grid-2 { grid-template-columns: 1fr; } }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
    }
    .card-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 16px; color: #fff; }
    /* Interactive Image Viewer */
    .viewer-container { position: relative; border-radius: 8px; overflow: hidden; background: #000; }
    .viewer-container img { width: 100%; height: auto; display: block; }
    .overlay-svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
    .overlay-rect { stroke-width: 3; fill-opacity: 0.2; pointer-events: auto; cursor: pointer; transition: all 0.2s; }
    .overlay-rect:hover { fill-opacity: 0.45; }
    .controls { display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
    button.btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s, border 0.2s;
    }
    button.btn:hover, button.btn.active {
      background: var(--accent);
      color: #000;
      border-color: var(--accent);
    }
    /* Swatches */
    .swatches { display: flex; gap: 12px; flex-wrap: wrap; }
    .swatch-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      background: rgba(255, 255, 255, 0.04);
      padding: 10px;
      border-radius: 8px;
      cursor: pointer;
      border: 1px solid var(--border);
      transition: transform 0.2s;
    }
    .swatch-item:hover { transform: translateY(-2px); border-color: var(--accent); }
    .swatch-color { width: 52px; height: 52px; border-radius: 6px; margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.1); }
    .swatch-hex { font-family: monospace; font-size: 0.85rem; font-weight: 700; }
    .swatch-role { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; }
    /* Evidence Table */
    table.data-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.95rem;
    }
    table.data-table th, table.data-table td {
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    table.data-table th { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); font-weight: 600; }
    .strength-meter {
      height: 6px;
      border-radius: 3px;
      background: #334155;
      width: 80px;
      overflow: hidden;
      display: inline-block;
      vertical-align: middle;
      margin-left: 8px;
    }
    .strength-fill { height: 100%; background: var(--accent); }
    /* Prompts & Code */
    pre.code-block {
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 0.9rem;
      color: #e2e8f0;
      position: relative;
      margin: 10px 0;
      white-space: pre-wrap;
    }
    .copy-btn {
      position: absolute;
      top: 10px;
      right: 10px;
      font-size: 0.75rem;
      padding: 4px 8px;
      border-radius: 4px;
      background: var(--border);
      border: none;
      color: #fff;
      cursor: pointer;
    }
    .copy-btn:hover { background: var(--accent); color: #000; }
    .review-alert {
      background: rgba(239, 68, 68, 0.12);
      border: 1px solid var(--danger);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
    }
    .review-title { font-weight: 700; color: #f87171; margin-bottom: 4px; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>rea-image Analysis Report</h1>
      <p style="color: var(--text-muted);">
        <strong>File:</strong> {{ report.image.path }} | 
        <strong>Dimensions:</strong> {{ report.image.width }}x{{ report.image.height }} ({{ report.image.aspect_ratio }}) | 
        <strong>Format:</strong> {{ report.image.format }} | 
        <strong>SHA256:</strong> <code>{{ report.image.sha256[:16] }}...</code>
      </p>
    </header>

    <!-- Hero Verdict Banner -->
    <section class="verdict-banner">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span class="verdict-title">VERDICT & CLASSIFICATION</span>
        <span class="badge badge-{{ 'high' if 'high' in report.verdict.confidence else ('medium' if 'medium' in report.verdict.confidence else 'low') }}">
          Confidence: {{ report.verdict.confidence }}
        </span>
      </div>
      <p class="verdict-summary">{{ report.verdict.summary }}</p>
      <div class="breakdown-bar">
        {% for b in report.verdict.method_breakdown %}
        <div class="breakdown-seg" style="width: {{ b.area_pct }}%; background: {{ '#38bdf8' if 'ai' in b.method.lower() else ('#10b981' if 'photo' in b.method.lower() else '#f59e0b') }};" title="{{ b.method }}: {{ b.area_pct }}%"></div>
        {% endfor %}
      </div>
    </section>

    <!-- Needs Review Section if contradictions exist -->
    {% if report.needs_review %}
    <section class="card" style="border-color: var(--danger);">
      <h2 class="card-title" style="color: #f87171;">⚠️ Needs Review / Conflicts Detected</h2>
      {% for item in report.needs_review %}
      <div class="review-alert">
        <div class="review-title">Region {{ item.region_id }}: {{ item.reason }}</div>
        <p><strong>Action for Reviewer / Agent:</strong> {{ item.question_for_agent }}</p>
      </div>
      {% endfor %}
    </section>
    {% endif %}

    <!-- Image Inspector & Palette -->
    <div class="grid-2">
      <section class="card">
        <h2 class="card-title">Image & Layer Inspector</h2>
        <div class="viewer-container" id="viewer">
          <img id="mainImg" src="original.png" alt="Original Image">
          <svg class="overlay-svg" id="overlaySvg" viewBox="0 0 {{ report.image.width }} {{ report.image.height }}">
            <!-- Composition grid (hidden by default) -->
            <g id="compositionGrid" style="display: none;">
              <line x1="{{ report.image.width / 3 }}" y1="0" x2="{{ report.image.width / 3 }}" y2="{{ report.image.height }}" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6,6" opacity="0.7"/>
              <line x1="{{ report.image.width * 2 / 3 }}" y1="0" x2="{{ report.image.width * 2 / 3 }}" y2="{{ report.image.height }}" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6,6" opacity="0.7"/>
              <line x1="0" y1="{{ report.image.height / 3 }}" x2="{{ report.image.width }}" y2="{{ report.image.height / 3 }}" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6,6" opacity="0.7"/>
              <line x1="0" y1="{{ report.image.height * 2 / 3 }}" x2="{{ report.image.width }}" y2="{{ report.image.height * 2 / 3 }}" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6,6" opacity="0.7"/>
            </g>
            <!-- Region Overlays -->
            <g id="regionRects">
              {% for r in report.regions %}
              <rect class="overlay-rect" id="rect-{{ r.id }}" x="{{ r.bbox[0] }}" y="{{ r.bbox[1] }}" width="{{ r.bbox[2] }}" height="{{ r.bbox[3] }}"
                    stroke="{{ '#38bdf8' if 'ai' in r.method.lower() else ('#10b981' if 'photo' in r.method.lower() else '#f59e0b') }}"
                    fill="{{ '#38bdf8' if 'ai' in r.method.lower() else ('#10b981' if 'photo' in r.method.lower() else '#f59e0b') }}"/>
              {% endfor %}
            </g>
          </svg>
        </div>
        <div class="controls">
          <button class="btn active" id="btnToggleRegions" onclick="toggleRegions()">Toggle Regions</button>
          <button class="btn" id="btnToggleGrid" onclick="toggleCompositionGrid()">Rule of Thirds Grid</button>
        </div>
      </section>

      <section class="card">
        <h2 class="card-title">Color Palette & Grading</h2>
        <div class="swatches">
          {% for c in report.global_analysis.palette %}
          <div class="swatch-item" onclick="copyHex('{{ c.hex }}')">
            <div class="swatch-color" style="background-color: {{ c.hex }};"></div>
            <span class="swatch-hex">{{ c.hex }}</span>
            <span class="swatch-role">{{ c.role }} ({{ c.percentage }}%)</span>
          </div>
          {% endfor %}
        </div>
        <div style="margin-top: 24px;">
          <h3 style="font-size: 1rem; margin-bottom: 8px;">Color Grade Parameters:</h3>
          <ul style="list-style: none; font-size: 0.9rem; color: var(--text-muted);">
            {% for k, v in report.global_analysis.color_grade.items() %}
            <li>• <strong>{{ k }}:</strong> {{ v }}</li>
            {% endfor %}
          </ul>
        </div>
      </section>
    </div>

    <!-- Typography & Layout Grid Analysis -->
    <div class="grid-2">
      <section class="card">
        <h2 class="card-title">Typography & Text Analysis</h2>
        <ul style="list-style: none; font-size: 0.9rem; color: var(--text-muted); line-height: 1.8;">
          <li>• <strong>Extracted Text:</strong> <span style="color: #fff;">{{ report.global_analysis.typography.extracted_text or 'not measured' }}</span></li>
          <li>• <strong>Hierarchy:</strong> {{ report.global_analysis.typography.size_hierarchy or 'not measured' }}</li>
          <li>• <strong>Weight:</strong> {{ report.global_analysis.typography.weight or 'not measured' }}</li>
          <li>• <strong>Alignment:</strong> {{ report.global_analysis.typography.alignment or 'not measured' }}</li>
          <li>• <strong>Line Spacing:</strong> {{ report.global_analysis.typography.line_spacing or 'not measured' }}</li>
          <li>• <strong>Tracking:</strong> {{ report.global_analysis.typography.tracking or 'not measured' }}</li>
          {% if report.global_analysis.typography.font_family_candidates %}
          <li>• <strong>Font Candidates:</strong> {{ report.global_analysis.typography.font_family_candidates | join(', ') }}</li>
          {% endif %}
        </ul>
      </section>

      <section class="card">
        <h2 class="card-title">Layout Grid & Margins</h2>
        <ul style="list-style: none; font-size: 0.9rem; color: var(--text-muted); line-height: 1.8;">
          <li>• <strong>Grid Type:</strong> {{ report.global_analysis.layout_grid.grid_type or 'not measured' }}</li>
          <li>• <strong>Alignment Axes:</strong> {{ report.global_analysis.layout_grid.alignment_axes or 'not measured' }}</li>
          <li>• <strong>Container Padding:</strong> {{ report.global_analysis.layout_grid.container_padding or 'not measured' }}</li>
          {% if report.global_analysis.layout_grid.margins is mapping %}
          <li>• <strong>Margins (T/R/B/L):</strong> {{ report.global_analysis.layout_grid.margins.top }}px / {{ report.global_analysis.layout_grid.margins.right }}px / {{ report.global_analysis.layout_grid.margins.bottom }}px / {{ report.global_analysis.layout_grid.margins.left }}px</li>
          {% else %}
          <li>• <strong>Margins:</strong> {{ report.global_analysis.layout_grid.margins or 'not measured' }}</li>
          {% endif %}
          <li>• <strong>Corner Radii:</strong> {{ report.global_analysis.layout_grid.corner_radii or 'not measured' }}</li>
          <li>• <strong>Card Patterns:</strong> {{ report.global_analysis.layout_grid.card_patterns or 'not measured' }}</li>
        </ul>
      </section>
    </div>

    <!-- Camera Hardware & Optical Profile -->
    {% if report.global_analysis.camera and report.global_analysis.camera.detected %}
    <section class="card" style="border-left: 4px solid var(--accent); margin-bottom: 24px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <h2 class="card-title" style="margin-bottom: 0;">📷 Camera Hardware & Optical Profile</h2>
        <span class="badge {{ 'badge-high' if report.global_analysis.camera.confidence == 'high' else 'badge-medium' }}">
          {{ report.global_analysis.camera.source | replace('_', ' ') | upper }} ({{ report.global_analysis.camera.confidence | upper }})
        </span>
      </div>
      <p style="font-size: 1.1rem; color: #fff; font-weight: 600; margin-bottom: 16px;">
        {{ report.global_analysis.camera.display_name }}
        <span style="font-size: 0.85rem; font-weight: normal; color: var(--text-muted); margin-left: 8px;">
          ({{ report.global_analysis.camera.device_type_label }} • {{ report.global_analysis.camera.sensor_format_label }})
        </span>
      </p>
      <div class="grid-2" style="margin-bottom: 0;">
        <ul style="list-style: none; font-size: 0.9rem; color: var(--text-muted); line-height: 1.8;">
          {% if report.global_analysis.camera.lens %}
          <li>• <strong>Lens Model:</strong> <span style="color: #fff;">{{ report.global_analysis.camera.lens }}</span></li>
          {% endif %}
          {% if report.global_analysis.camera.focal_length %}
          <li>• <strong>Focal Length:</strong> {{ report.global_analysis.camera.focal_length }}{% if report.global_analysis.camera.focal_length_35mm %} (35mm eq: {{ report.global_analysis.camera.focal_length_35mm }}){% endif %}</li>
          {% endif %}
          {% if report.global_analysis.camera.aperture %}
          <li>• <strong>Aperture:</strong> {{ report.global_analysis.camera.aperture }}</li>
          {% endif %}
          {% if report.global_analysis.camera.shutter_speed %}
          <li>• <strong>Shutter Speed:</strong> {{ report.global_analysis.camera.shutter_speed }}</li>
          {% endif %}
          {% if report.global_analysis.camera.iso %}
          <li>• <strong>ISO Sensitivity:</strong> ISO {{ report.global_analysis.camera.iso }}</li>
          {% endif %}
        </ul>
        <ul style="list-style: none; font-size: 0.9rem; color: var(--text-muted); line-height: 1.8;">
          {% if report.global_analysis.camera.exposure_program %}
          <li>• <strong>Exposure Program:</strong> {{ report.global_analysis.camera.exposure_program }}</li>
          {% endif %}
          {% if report.global_analysis.camera.software_firmware %}
          <li>• <strong>OS / Firmware:</strong> {{ report.global_analysis.camera.software_firmware }}</li>
          {% endif %}
          {% if report.global_analysis.camera.optical_signatures %}
          <li>• <strong>Depth of Field:</strong> {{ report.global_analysis.camera.optical_signatures.depth_of_field or 'Standard' }}</li>
          <li>• <strong>Vignette Profile:</strong> {{ report.global_analysis.camera.optical_signatures.vignette_falloff or 'Natural' }}</li>
          {% endif %}
          {% if report.global_analysis.camera.computational_traces %}
          <li>• <strong>Computational Traces:</strong> {{ report.global_analysis.camera.computational_traces | join('; ') }}</li>
          {% endif %}
        </ul>
      </div>
    </section>
    {% endif %}

    <!-- Per-Region Cards -->
    <section class="card">
      <h2 class="card-title">Decomposed Regions & Recreation Plans</h2>
      {% for r in report.regions %}
      <div class="card" style="background: rgba(255,255,255,0.02); margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <strong style="font-size: 1.1rem; color: #fff;">{{ r.id }} ({{ r.label }})</strong>
            <span style="color: var(--text-muted); font-size: 0.9rem; margin-left: 8px;">Area: {{ r.area_pct }}% | BBox: [{{ r.bbox | join(', ') }}]</span>
          </div>
          <span class="badge badge-high">{{ r.method }} ({{ r.confidence }})</span>
        </div>
        
        <div class="grid-2">
          <div>
            {% if r.crop_path %}
            <img src="{{ r.crop_path }}" alt="Region crop" style="max-height: 180px; border-radius: 6px; border: 1px solid var(--border); margin-bottom: 12px;">
            {% endif %}
            <h4 style="font-size: 0.95rem; margin-bottom: 6px;">Recreation Route: <span style="color: var(--accent); text-transform: uppercase;">{{ r.recreate.path }}</span> (Cost: {{ r.recreate.est_cost }}, Time: {{ r.recreate.est_time }})</h4>
            <ul style="font-size: 0.85rem; color: var(--text-muted); padding-left: 18px;">
              {% for step in r.recreate.steps %}
              <li>{{ step }}</li>
              {% endfor %}
            </ul>
          </div>
          <div>
            {% if r.reverse and r.reverse.prompt %}
            <h4 style="font-size: 0.95rem;">Reverse Prompt:</h4>
            <pre class="code-block"><button class="copy-btn" onclick="navigator.clipboard.writeText('{{ r.reverse.prompt | replace("'", "\\'") }}')">Copy</button>{{ r.reverse.prompt }}</pre>
            {% endif %}
            {% if r.top_contradicting %}
            <div style="margin-top: 10px;">
              <span style="font-size: 0.85rem; color: #f87171; font-weight: 600;">Contradicting Signals:</span>
              <ul style="font-size: 0.8rem; color: var(--text-muted); padding-left: 18px; margin-top: 4px;">
                {% for cev in r.top_contradicting %}
                <li><strong>{{ cev.name }}</strong> ({{ cev.direction }}, strength {{ "%.2f"|format(cev.strength) }}): {{ cev.explanation }}</li>
                {% endfor %}
              </ul>
            </div>
            {% endif %}
          </div>
        </div>
      </div>
      {% endfor %}
    </section>

    <!-- Comprehensive Evidence Table -->
    <section class="card">
      <h2 class="card-title">Evidence & Signal Traceability</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Signal / Detector</th>
            <th>Region</th>
            <th>Supports Method</th>
            <th>Strength</th>
            <th>Observed Evidence Explanation</th>
          </tr>
        </thead>
        <tbody>
          {% for r in report.regions %}
            {% for ev in r.evidence %}
            <tr>
              <td><code>{{ ev.name }}</code></td>
              <td>{{ ev.region }}</td>
              <td><strong>{{ ev.direction }}</strong></td>
              <td>
                {{ "%.2f"|format(ev.strength) }}
                <div class="strength-meter"><div class="strength-fill" style="width: {{ ev.strength * 100 }}%;"></div></div>
              </td>
              <td>{{ ev.explanation }}</td>
            </tr>
            {% endfor %}
          {% endfor %}
        </tbody>
      </table>
    </section>

    <!-- Limitations and Ethics -->
    <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.85rem;">
      <p><strong>Methodological Limitations & Ethical Purpose:</strong> Classification results are based on probabilistic metadata, frequency, and forensic analysis. This tool is intended for technical study and creative recreation with authorized assets. Never use this output as a definitive accusation of authenticity against individuals.</p>
    </footer>
  </div>

  <script>
    function toggleRegions() {
      const g = document.getElementById('regionRects');
      const btn = document.getElementById('btnToggleRegions');
      if (g.style.display === 'none') {
        g.style.display = 'block';
        btn.classList.add('active');
      } else {
        g.style.display = 'none';
        btn.classList.remove('active');
      }
    }
    function toggleCompositionGrid() {
      const g = document.getElementById('compositionGrid');
      const btn = document.getElementById('btnToggleGrid');
      if (g.style.display === 'none') {
        g.style.display = 'block';
        btn.classList.add('active');
      } else {
        g.style.display = 'none';
        btn.classList.remove('active');
      }
    }
    function copyHex(hex) {
      navigator.clipboard.writeText(hex);
      alert('Copied color hex: ' + hex);
    }
  </script>
</body>
</html>
"""


def generate_report_html(report_data: ReportSchema, output_file: Path) -> Path:
    """Render and write self-contained interactive report.html."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    template = Template(HTML_TEMPLATE)
    html_content = template.render(report=report_data)
    output_file.write_text(html_content, encoding="utf-8")
    return output_file

