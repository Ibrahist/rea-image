"""UI / Screenshot scaffold generator: design tokens, component hierarchy, and HTML/CSS."""

from typing import List, Optional
from rea_image.schemas import PaletteColor, RegionAnalysis


class UIScaffoldBuilder:
    """Generates HTML/CSS components and design tokens reproducing UI layouts."""

    def build_html_css(
        self,
        palette: List[PaletteColor],
        regions: Optional[List[RegionAnalysis]] = None,
    ) -> str:
        bg = palette[0].hex if palette else "#0F172A"
        accent = next((p.hex for p in palette if p.role == "accent"), "#3B82F6")
        text = next((p.hex for p in palette if p.role == "text"), "#F8FAFC")
        card_bg = next((p.hex for p in palette if p.role == "subject"), "#1E293B")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reconstructed UI Layout</title>
  <style>
    :root {{
      --bg-primary: {bg};
      --bg-card: {card_bg};
      --color-accent: {accent};
      --text-main: {text};
      --radius-sm: 8px;
      --radius-md: 16px;
      --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: var(--bg-primary);
      color: var(--text-main);
      font-family: var(--font-stack);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 24px;
    }}
    .ui-container {{
      width: 100%;
      max-width: 960px;
      background: var(--bg-card);
      border-radius: var(--radius-md);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
      padding: 32px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}
    .ui-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding-bottom: 16px;
    }}
    .ui-title {{
      font-size: 1.5rem;
      font-weight: 700;
    }}
    .ui-btn {{
      background: var(--color-accent);
      color: #FFFFFF;
      padding: 10px 20px;
      border-radius: var(--radius-sm);
      border: none;
      font-weight: 600;
      cursor: pointer;
    }}
    .ui-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 20px;
    }}
    .ui-card {{
      background: rgba(255, 255, 255, 0.05);
      border-radius: var(--radius-sm);
      padding: 20px;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .user-content-note {{
      font-size: 0.85rem;
      color: #94A3B8;
      margin-top: 12px;
      font-style: italic;
    }}
  </style>
</head>
<body>
  <div class="ui-container">
    <header class="ui-header">
      <h1 class="ui-title">Application Dashboard</h1>
      <button class="ui-btn">Action Button</button>
    </header>
    <main class="ui-grid">
      <div class="ui-card">
        <h3>Feature Metric</h3>
        <p class="user-content-note">※ Note: Populate with user production data</p>
      </div>
      <div class="ui-card">
        <h3>Primary Activity</h3>
        <p class="user-content-note">※ Note: Insert live user avatar / records</p>
      </div>
    </main>
  </div>
</body>
</html>
"""
        return html

