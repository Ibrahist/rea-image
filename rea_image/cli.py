"""CLI interface for rea-image using Typer and Rich."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    name="rea-image",
    help="Reverse-engineer any still image: how it was made, evidence, and recreation plan.",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    target: Path = typer.Argument(..., help="Path to an image file or directory of images."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output directory for reports and layers."),
    vlm: Optional[str] = typer.Option(None, "--vlm", help="VLM model identifier for visual review."),
    offline: bool = typer.Option(True, "--offline/--online", help="Force offline mode with no network calls."),
    agent_review: bool = typer.Option(False, "--agent-review", help="Export inspection tasks for agent review."),
    open_browser: bool = typer.Option(False, "--open", help="Open the generated report.html in default browser."),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively search directory for images."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, or csv."),
):
    """Analyze one image or a folder of images to reverse-engineer production methods."""
    import csv
    import io
    import json
    from rea_image.ingest.loader import IngestError
    from rea_image.report.orchestrator import run_analysis_pipeline

    fmt = output_format.lower().strip()
    if fmt not in ("table", "json", "csv"):
        console.print(f"[bold red]Error:[/bold red] Unsupported format '{output_format}'. Choose table, json, or csv.")
        raise typer.Exit(code=1)

    if not target.exists():
        if fmt == "table":
            console.print(f"[bold red]Error:[/bold red] Target path does not exist: {target}")
        raise typer.Exit(code=1)

    image_paths = []
    if target.is_dir():
        glob_func = target.rglob if recursive else target.glob
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tiff", ".tif", ".bmp", ".avif"):
            image_paths.extend(glob_func(f"*{ext}"))
            image_paths.extend(glob_func(f"*{ext.upper()}"))
        image_paths = sorted(set(image_paths))
        if not image_paths:
            if fmt == "table":
                console.print(f"[yellow]No supported images found in directory: {target}[/yellow]")
            elif fmt == "json":
                console.print("[]")
            raise typer.Exit(code=0)
    else:
        image_paths = [target]

    if fmt == "table":
        console.print(f"[bold cyan]rea-image analysis[/bold cyan] - processing {len(image_paths)} image(s)...")

    all_reports = []
    batch_records = []
    failures = 0
    for img_path in image_paths:
        try:
            target_out = (out / img_path.stem) if (out and len(image_paths) > 1) else out
            report = run_analysis_pipeline(
                image_path=img_path,
                out_dir=target_out,
                offline=offline,
                vlm_model=vlm,
                agent_review=agent_review,
            )
            all_reports.append(report)
            resolved_dir = target_out or Path(f"./rea_output/{img_path.stem}")

            record = {
                "image": img_path.name,
                "image_path": str(img_path),
                "verdict": report.verdict.summary,
                "dominant_method": report.verdict.method_breakdown[0].method if report.verdict.method_breakdown else "unknown",
                "confidence": report.verdict.confidence,
                "aspect_ratio": report.image.aspect_ratio,
                "width": report.image.width,
                "height": report.image.height,
                "reports_dir": str(resolved_dir),
            }
            batch_records.append(record)

            if fmt == "table":
                console.print(f"\n[bold green]✓ Analysis complete for {img_path.name}[/bold green]")
                console.print(f"  [bold]Verdict:[/bold] {report.verdict.summary}")
                console.print(f"  [bold]Reports saved to:[/bold] {resolved_dir}")
            
            if open_browser:
                import webbrowser
                html_file = resolved_dir / "report.html"
                if html_file.exists():
                    webbrowser.open(html_file.resolve().as_uri())
        except IngestError as e:
            failures += 1
            batch_records.append({
                "image": img_path.name,
                "image_path": str(img_path),
                "verdict": f"IngestError: {e}",
                "dominant_method": "error",
                "confidence": "none",
                "aspect_ratio": "unknown",
                "width": 0,
                "height": 0,
                "reports_dir": "",
            })
            if fmt == "table":
                console.print(f"[bold red]Failed to ingest {img_path.name}:[/bold red] {e}")
        except Exception as e:
            failures += 1
            batch_records.append({
                "image": img_path.name,
                "image_path": str(img_path),
                "verdict": f"Error: {e}",
                "dominant_method": "error",
                "confidence": "none",
                "aspect_ratio": "unknown",
                "width": 0,
                "height": 0,
                "reports_dir": "",
            })
            if fmt == "table":
                console.print(f"[bold red]Pipeline error on {img_path.name}:[/bold red] {e}")

    # Generate batch_summary.csv for directory runs
    if target.is_dir() and batch_records:
        series_dir = out or Path("./rea_output")
        series_dir.mkdir(parents=True, exist_ok=True)
        csv_file = series_dir / "batch_summary.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["image", "verdict", "dominant_method", "confidence", "aspect_ratio", "width", "height", "reports_dir"]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in batch_records:
                writer.writerow(r)
        if fmt == "table":
            console.print(f"\n[green]✓ Batch summary CSV exported to {csv_file}[/green]")

    # Machine-readable output formatting
    if fmt == "json":
        console.print_json(json.dumps(batch_records if len(batch_records) > 1 else (batch_records[0] if batch_records else {})))
    elif fmt == "csv":
        out_buf = io.StringIO()
        fieldnames = ["image", "verdict", "dominant_method", "confidence", "aspect_ratio", "width", "height", "reports_dir"]
        writer = csv.DictWriter(out_buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in batch_records:
            writer.writerow(r)
        console.print(out_buf.getvalue().strip())

    # Cross-image consistency summary if analyzing a folder of images
    if target.is_dir() and len(all_reports) > 1 and fmt == "table":
        from rea_image.report.consistency import analyze_cross_image_consistency
        series_dir = out or Path("./rea_output")
        consistency = analyze_cross_image_consistency(all_reports, out_dir=series_dir)
        
        console.print("\n" + "=" * 60)
        console.print(Panel(
            f"[bold cyan]Cross-Image Series Consistency Summary[/bold cyan]\n"
            f"Series Verdict: [bold]{consistency['series_verdict']}[/bold] (Score: {consistency['series_cohesion_score']}/100)\n"
            f"• Uniform Aspect Ratio: {'Yes' if consistency['aspect_ratio_consistency']['is_uniform'] else 'No (' + ', '.join(consistency['aspect_ratio_consistency']['unique_aspect_ratios']) + ')'}\n"
            f"• Production Medium: {consistency['production_method_consistency']['dominant_method']} ({'Uniform' if consistency['production_method_consistency']['is_uniform'] else 'Mixed'})\n"
            f"• Palette Cohesion: {consistency['palette_cohesion']['level'].capitalize()}\n"
            f"• Consistency JSON: {series_dir / 'consistency_summary.json'}",
            expand=False,
        ))

    if failures > 0:
        raise typer.Exit(code=1)


@app.command()
def report(
    out_dir: Path = typer.Argument(..., help="Output directory containing report.json to rebuild report.html."),
    open_browser: bool = typer.Option(False, "--open", help="Open rebuilt report.html in default browser."),
):
    """Rebuild report.html from report.json in an existing output directory."""
    from rea_image.report.orchestrator import rebuild_html_from_json
    
    json_path = out_dir / "report.json"
    if not json_path.exists():
        console.print(f"[bold red]Error:[/bold red] report.json not found in {out_dir}")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Rebuilding HTML report in {out_dir}...[/cyan]")
    html_path = rebuild_html_from_json(out_dir)
    console.print(f"[green]✓ Successfully rebuilt report.html at {html_path}[/green]")
    if open_browser:
        import webbrowser
        webbrowser.open(html_path.resolve().as_uri())


@app.command()
def explain(
    out_dir: Path = typer.Argument(..., help="Output directory containing report.json."),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Region ID to explain (default: all regions)."),
):
    """Print the evidence ledger behind a verdict (each item, weight, signed contribution)."""
    import json
    from rea_image.judge.engine import DETECTOR_CATEGORY_WEIGHTS

    json_path = out_dir / "report.json" if out_dir.is_dir() else out_dir
    if not json_path.exists():
        console.print(f"[bold red]Error:[/bold red] report.json not found in {out_dir}")
        raise typer.Exit(code=1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    verdict_summary = data.get("verdict", {}).get("summary", "Unknown")
    regions = data.get("regions", [])

    if region:
        target_regions = [r for r in regions if r.get("id") == region]
        if not target_regions:
            valid_ids = [r.get("id") for r in regions]
            console.print(f"[bold red]Error:[/bold red] Region '{region}' not found. Available regions: {', '.join(valid_ids)}")
            raise typer.Exit(code=1)
    else:
        target_regions = regions

    console.print(Panel(
        f"[bold cyan]rea-image Evidence Ledger & Verdict Explanation[/bold cyan]\n"
        f"Verdict: [bold]{verdict_summary}[/bold]",
        expand=False,
    ))

    for r in target_regions:
        r_id = r.get("id", "unknown")
        r_label = r.get("label", "unknown")
        r_method = r.get("method", "unknown")
        r_conf = r.get("confidence", "unknown")
        r_evidence = r.get("evidence", [])

        table = Table(
            title=f"Region {r_id} ({r_label}) — Predicted: {r_method} ({r_conf})",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Detector / Signal", style="cyan")
        table.add_column("Direction", style="white")
        table.add_column("Strength", justify="right")
        table.add_column("Weight", justify="right")
        table.add_column("Signed Score", justify="right")
        table.add_column("Explanation", style="white")

        total_signed = 0.0
        for ev in r_evidence:
            name = ev.get("name", "")
            direction = ev.get("direction", "")
            strength = float(ev.get("strength", 0.0))
            cat_weight = DETECTOR_CATEGORY_WEIGHTS.get(name, 1.0)
            reg_mult = 1.5 if ev.get("region") == r_id else 1.0
            eff_weight = cat_weight * reg_mult

            if direction == r_method:
                signed = eff_weight * strength
                score_str = f"[green]+{signed:.2f}[/green]"
            elif direction == "neutral":
                signed = 0.0
                score_str = "[dim]0.00[/dim]"
            else:
                signed = -(eff_weight * strength)
                score_str = f"[red]{signed:.2f}[/red]"

            total_signed += signed
            table.add_row(
                name,
                direction,
                f"{strength:.2f}",
                f"{eff_weight:.1f}x",
                score_str,
                ev.get("explanation", ""),
            )

        console.print(table)
        net_style = "green" if total_signed >= 0 else "red"
        console.print(f"  [bold]Net Signed Support for '{r_method}':[/bold] [{net_style}]{total_signed:+.2f}[/{net_style}]\n")


@app.command(name="apply-review")
def apply_review(
    out_dir: Path = typer.Argument(..., help="Output directory containing report.json and review_tasks.json."),
    answers: Optional[Path] = typer.Option(None, "--answers", "-a", help="Path to completed review answers JSON file."),
):
    """Apply agent or human visual review decisions to resolve conflicts and update the report."""
    from rea_image.report.agent_review import apply_agent_review

    try:
        updated_report = apply_agent_review(out_dir=out_dir, answers_file=answers)
        console.print("[bold green]✓ Agent review applied successfully![/bold green]")
        console.print(f"  [bold]Updated Verdict:[/bold] {updated_report.verdict.summary}")
        console.print(f"  [bold]Regenerated Artifacts:[/bold] report.json, report.html, verdict.txt in {out_dir}")
    except Exception as e:
        console.print(f"[bold red]Failed to apply review:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def prompt(
    image: Path = typer.Argument(..., help="Path to image file."),
):
    """Extract or reverse-engineer generation prompt only."""
    from rea_image.ingest.loader import load_image
    from rea_image.evidence import GeneratorTracesDetector
    from rea_image.reverse.prompt_builder import PromptBuilder

    res = load_image(image)
    console.print(Panel(f"[bold cyan]Reverse Prompt Analysis[/bold cyan]: {image.name}", expand=False))

    # Check embedded metadata first
    traces = GeneratorTracesDetector().run(res)
    has_meta_prompt = False
    for ev in traces:
        if ev.name == "ai_generator_metadata" and ev.value.get("prompt"):
            has_meta_prompt = True
            console.print(f"[bold green]Embedded Generator Prompt Found ({ev.value.get('generator')}):[/bold green]")
            console.print(f"\"{ev.value['prompt']}\"\n")
            if ev.value.get("negative_prompt"):
                console.print(f"[bold magenta]Negative Prompt:[/bold magenta]\n\"{ev.value['negative_prompt']}\"\n")

    if not has_meta_prompt:
        console.print("[yellow]No embedded metadata prompt found. Generating reverse-engineered prompt...[/yellow]")
        from rea_image.evidence.craft_camera import CameraCraftEstimator
        from rea_image.evidence.craft_lighting import LightingClassifier
        from rea_image.evidence.craft_color import analyze_color_grade, extract_dominant_palette
        from rea_image.segment import segment_image
        from rea_image.judge import JudgmentEngine, VerdictAggregator
        from rea_image.evidence import (
            ForensicsNoiseDetector,
            ForensicsJpegDetector,
            ForensicsFrequencyDetector,
            ForensicsFlatDetector,
            VisualChecksDetector,
            ProvenanceDetector,
            ExportTracesDetector,
        )

        arr = res.rgb_array
        seg_regions = segment_image(arr, offline=True)
        camera_info = CameraCraftEstimator().estimate(arr, seg_regions)
        lighting_info = LightingClassifier().classify(arr)
        color_grade = analyze_color_grade(arr)
        palette = extract_dominant_palette(arr, n_colors=6)

        detectors = [
            ProvenanceDetector(),
            GeneratorTracesDetector(),
            ExportTracesDetector(),
            ForensicsNoiseDetector(),
            ForensicsJpegDetector(),
            ForensicsFrequencyDetector(),
            ForensicsFlatDetector(),
            VisualChecksDetector(),
        ]
        evidence = []
        for d in detectors:
            evidence.extend(d.run(res, seg_regions))

        judge = JudgmentEngine()
        reg_verdicts = []
        for r in seg_regions:
            va, _, _ = judge.judge_region(r.id, r.label, r.bbox, r.area_pct, evidence)
            reg_verdicts.append(va)
        verdict, _ = VerdictAggregator().aggregate(
            reg_verdicts,
            evidence,
            aspect_ratio=res.metadata.aspect_ratio,
            width=res.metadata.width,
            height=res.metadata.height,
            color_grade=color_grade,
        )

        dominant_colors = [c.hex for c in palette[:3]]
        palette_desc = f"palette featuring {', '.join(dominant_colors)}"
        subject_desc = f"subject with {palette_desc}"
        lighting_dict = lighting_info.model_dump() if hasattr(lighting_info, "model_dump") else (lighting_info or {})
        setting_desc = f"{lighting_dict.get('matched_setup', 'natural environment').lower()} setting"
        style_desc = f"{verdict.summary} aesthetic"

        p_info = PromptBuilder().build(
            subject_desc=subject_desc,
            setting_desc=setting_desc,
            style_desc=style_desc,
            camera_lens=camera_info,
            lighting_info=lighting_dict,
            color_info=color_grade,
            aspect_ratio=res.metadata.aspect_ratio,
        )
        console.print(f"\n[bold]Reconstructed Prompt (Faithful):[/bold]\n\"{p_info.prompt}\"")
        console.print(f"\n[bold]Reconstructed Prompt (Simplified):[/bold]\n\"{p_info.variants['simplified']}\"")
        console.print(f"\n[bold magenta]Negative Prompt:[/bold magenta]\n\"{p_info.negative_prompt}\"")


@app.command()
def recreate(
    out_dir: Path = typer.Argument(..., help="Output directory containing the replication plan."),
    dry_run: bool = typer.Option(True, "--dry-run", help="Simulate recreation without calling backends."),
    confirm: bool = typer.Option(False, "--confirm", help="Explicitly confirm paid/active model execution."),
):
    """Execute or preview the recreation plan through configured generation backends."""
    import json
    from rea_image.replicate.backend import GenerationBackend

    json_path = out_dir / "report.json"
    if not json_path.exists():
        console.print(f"[bold red]Error:[/bold red] report.json not found in {out_dir}")
        raise typer.Exit(code=1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    regions = data.get("regions", [])
    backend = GenerationBackend()
    console.print(Panel(f"[bold cyan]Recreation Plan Runner[/bold cyan] (Dry Run: {dry_run}, Confirmed: {confirm})", expand=False))

    has_generated = False
    for r in regions:
        recreate_info = r.get("recreate") or {}
        r_path = recreate_info.get("path")
        if not r_path:
            console.print(f"• Region [bold]{r.get('id', 'unknown')}[/bold] ({r.get('label', 'unknown')}): [yellow]SKIPPED[/yellow] (no path specified)")
            continue
        console.print(f"• Region [bold]{r.get('id')}[/bold] ({r.get('label')}): [green]{r_path.upper()}[/green] via {', '.join(recreate_info.get('tools', []))}")

        if r_path == "generate":
            has_generated = True
            rev = r.get("reverse", {})
            prompt_str = rev.get("prompt", "detailed scene")
            neg_prompt = rev.get("negative_prompt", "")
            cost = recreate_info.get("est_cost", "$0.02")

            backend.execute_recreation(
                prompt=prompt_str,
                negative_prompt=neg_prompt,
                model_name="FLUX.1 [dev]",
                aspect_ratio=data.get("image", {}).get("aspect_ratio", "1:1"),
                est_cost=cost,
                dry_run=dry_run,
                confirmed=confirm,
            )

    if not has_generated:
        console.print("\n[yellow]No external AI generation required for this image. All regions route to offline design/shoot tools.[/yellow]")


@app.command()
def palette(
    image: Path = typer.Argument(..., help="Path to image file."),
):
    """Extract dominant palette and color-grade only."""
    from rea_image.ingest.loader import load_image
    from rea_image.evidence.craft_color import extract_dominant_palette, analyze_color_grade

    res = load_image(image)
    colors = extract_dominant_palette(res.rgb_array, n_colors=6)
    grade = analyze_color_grade(res.rgb_array)

    console.print(Panel(f"[bold cyan]Color Palette & Grading Analysis[/bold cyan]: {image.name}", expand=False))

    table = Table(title="Dominant Palette", show_header=True, header_style="bold magenta")
    table.add_column("Swatch", justify="center")
    table.add_column("Hex", style="cyan")
    table.add_column("RGB", style="white")
    table.add_column("Role", style="green")
    table.add_column("Area %", justify="right")

    for col in colors:
        swatch = f"[{col.hex}]██████[/{col.hex}]"
        rgb_str = f"({col.rgb[0]}, {col.rgb[1]}, {col.rgb[2]})"
        table.add_row(swatch, col.hex, rgb_str, col.role, f"{col.percentage:.1f}%")

    console.print(table)

    console.print("\n[bold]Color Grading Attributes:[/bold]")
    for k, v in grade.items():
        console.print(f"  • [cyan]{k}[/cyan]: {v}")


@app.command()
def provenance(
    image: Path = typer.Argument(..., help="Path to image file."),
):
    """Inspect metadata, C2PA credentials, and AI generator traces only."""
    from rea_image.ingest.loader import load_image
    from rea_image.evidence.provenance import ProvenanceDetector
    from rea_image.evidence.generator_traces import GeneratorTracesDetector
    from rea_image.evidence.export_traces import ExportTracesDetector

    res = load_image(image)
    console.print(Panel(f"[bold cyan]Provenance & Metadata Analysis[/bold cyan]: {image.name}", expand=False))

    all_evidence = []
    all_evidence.extend(ProvenanceDetector().run(res))
    all_evidence.extend(GeneratorTracesDetector().run(res))
    all_evidence.extend(ExportTracesDetector().run(res))

    table = Table(title="Detected Provenance Signals", show_header=True, header_style="bold magenta")
    table.add_column("Detector / Signal", style="cyan")
    table.add_column("Direction", style="green")
    table.add_column("Strength", justify="right")
    table.add_column("Explanation", style="white")

    for ev in all_evidence:
        table.add_row(ev.name, ev.direction, f"{ev.strength:.2f}", ev.explanation)

    console.print(table)





@app.command(name="eval")
def eval_dataset(
    dataset: Path = typer.Argument(Path("eval/benchmark_data/dataset.json"), help="Path to evaluation dataset manifest or directory."),
    tolerance: float = typer.Option(20.0, "--tolerance", "-t", help="Max allowed calibration error tolerance percentage before failing."),
):
    """Run the evaluation harness on a labeled dataset."""
    from eval.runner import run_evaluation
    
    if dataset.suffix.lower() == ".json":
        results_path = dataset.parent.parent / "RESULTS.md"
    else:
        results_path = dataset / "RESULTS.md"
    
    console.print(Panel(f"[bold cyan]Running rea-image Evaluation Harness[/bold cyan]\nDataset: {dataset}\nOutput: {results_path}", expand=False))
    
    summary = run_evaluation(dataset_manifest=dataset, results_output=results_path, calib_tolerance=tolerance)
    console.print("[bold green]✓ Evaluation Complete![/bold green]")
    console.print(f"  • Total benchmark items: [cyan]{summary.total_images}[/cyan]")
    console.print(f"  • Tuning Set Accuracy: [green]{summary.tuning_accuracy_pct}%[/green]")
    console.print(f"  • Held-Out Accuracy: [green]{summary.held_out_accuracy_pct}%[/green]")
    console.print(f"  • Original Files Accuracy: [green]{summary.original_accuracy_pct}%[/green]")
    console.print(f"  • Platform-Compressed Accuracy: [green]{summary.compressed_accuracy_pct}%[/green]")
    console.print(f"  • Screenshot Accuracy: [green]{summary.screenshot_accuracy_pct}%[/green]")
    console.print(f"\nDetailed report written to [bold]{results_path}[/bold]")

    if not summary.is_calibrated:
        for err in summary.calibration_errors:
            console.print(f"[bold red]Calibration Error:[/bold red] {err}")
        console.print(f"[bold red]Evaluation failed:[/bold red] Confidence calibration exceeds {tolerance}% tolerance.")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
