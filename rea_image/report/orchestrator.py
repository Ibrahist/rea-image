"""Full analysis pipeline orchestrator connecting all stages M1-M8."""

import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from rea_image import __version__

from rea_image.ingest.loader import load_image
from rea_image.segment.model_hook import segment_image
from rea_image.evidence import (
    extract_dominant_palette,
    analyze_color_grade,
    analyze_composition,
    CameraCraftEstimator,
    LightingClassifier,
    TypographyAnalyzer,
    analyze_layout_grid,
    get_active_detectors,
)
from rea_image.evidence.camera_detector import CameraDetector
from rea_image.judge import JudgmentEngine, VerdictAggregator
from rea_image.reverse import (
    PromptBuilder,
    PhotoShootPlanner,
    RenderScaffoldBuilder,
    GraphicScaffoldBuilder,
    UIScaffoldBuilder,
)
from rea_image.replicate import ReplicationPlanner
from rea_image.cache import default_cache
from rea_image.evidence.vlm_client import VLMClient
from rea_image.schemas import (
    GlobalAnalysis,
    ReportSchema,
    NeedsReviewItem,
    EvidenceItem,
    ProductionMethod,
    LightingSetupInfo,
    PaletteColor,
    CompositionInfo,
)
from rea_image.report.json_exporter import export_report_json
from rea_image.report.html_generator import generate_report_html
from rea_image.report.assets_exporter import export_assets_bundle


def compute_detectors_fingerprint(detectors: list) -> str:
    """Compute SHA-256 fingerprint from detector class names, source code, run methods, and source files."""
    parts = []
    for d in sorted(detectors, key=lambda x: type(x).__name__):
        cls = d.__class__
        parts.append(cls.__name__)
        try:
            parts.append(inspect.getsource(cls))
        except Exception:
            pass
        try:
            parts.append(inspect.getsource(d.run))
        except Exception:
            pass
        try:
            code = getattr(d.run, "__code__", None)
            if code:
                parts.append(str(code.co_code))
                parts.append(str(code.co_consts))
        except Exception:
            pass
        try:
            file_path = inspect.getsourcefile(cls)
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    parts.append(hashlib.sha256(f.read()).hexdigest())
        except Exception:
            pass
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()[:16]


def compute_craft_fingerprint() -> str:
    """Compute SHA-256 fingerprint from craft-analysis classes, functions, and source files."""
    from rea_image.evidence.camera_detector import classify_camera_device

    craft_targets = [
        CameraCraftEstimator,
        CameraDetector,
        classify_camera_device,
        LightingClassifier,
        extract_dominant_palette,
        analyze_color_grade,
        analyze_composition,
    ]
    parts = []
    for target in craft_targets:
        parts.append(getattr(target, "__name__", str(target)))
        try:
            parts.append(inspect.getsource(target))
        except Exception:
            pass
        if inspect.isclass(target):
            for attr in ("detect", "infer_from_optics", "extract_hardware_exif", "estimate", "classify"):
                meth = getattr(target, attr, None)
                if meth and callable(meth):
                    try:
                        parts.append(inspect.getsource(meth))
                    except Exception:
                        pass
                    try:
                        code = getattr(meth, "__code__", None)
                        if code:
                            parts.append(str(code.co_code))
                            parts.append(str(code.co_consts))
                    except Exception:
                        pass
        try:
            file_path = inspect.getsourcefile(target)
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    parts.append(hashlib.sha256(f.read()).hexdigest())
        except Exception:
            pass

    # Include raw content hash of cameras.yaml catalog
    try:
        yaml_path = Path(__file__).parent.parent / "capabilities" / "cameras.yaml"
        if yaml_path.exists():
            with open(yaml_path, "rb") as f:
                parts.append(hashlib.sha256(f.read()).hexdigest())
    except Exception:
        pass

    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()[:16]


def run_analysis_pipeline(
    image_path: Path,
    out_dir: Optional[Path] = None,
    offline: bool = True,
    vlm_model: Optional[str] = None,
    agent_review: bool = False,
    disabled_detectors: Optional[List[str]] = None,
    no_cache: bool = False,
    redact_metadata: bool = False,
) -> ReportSchema:
    """Run full end-to-end rea-image analysis pipeline on target image."""
    img_path = Path(image_path)
    if out_dir is None:
        out_dir = Path("./rea_output") / img_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: Ingest
    ingest_res = load_image(img_path)
    arr = ingest_res.rgb_array
    h, w, _ = arr.shape

    # Stage 2: Segmentation
    seg_regions, confirmed_text_boxes = segment_image(arr, offline=offline, vlm_model=vlm_model, return_text_boxes=True)

    # Fingerprints for cache keys
    sha256 = ingest_res.metadata.sha256
    seg_summary = [(r.id, r.label, r.bbox, round(r.area_pct, 2)) for r in seg_regions]
    seg_fingerprint = hashlib.sha256(json.dumps(seg_summary, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    # Stage 3: Evidence Collection
    skipped_detectors: List[str] = []
    detectors = get_active_detectors(disabled=disabled_detectors, skipped_detectors=skipped_detectors)
    det_fingerprint = compute_detectors_fingerprint(detectors)

    ev_meta = json.dumps({"version": __version__, "detectors": det_fingerprint, "seg": seg_fingerprint}, sort_keys=True)
    cache_ev_key = f"evidence_{hashlib.sha256(ev_meta.encode('utf-8')).hexdigest()[:16]}"

    cached_ev = None if no_cache else default_cache.get(sha256, cache_ev_key)
    if cached_ev is not None:
        global_evidence = [EvidenceItem(**item) for item in cached_ev]
    else:
        global_evidence = []
        for d in detectors:
            global_evidence.extend(d.run(ingest_res, seg_regions))
        if not no_cache:
            default_cache.set(sha256, cache_ev_key, [it.model_dump() for it in global_evidence])

    # Optional VLM Semantic Sanity Checks (Opt-in only when online, run outside deterministic cache)
    if (not offline) or vlm_model:
        vlm_key_data = json.dumps({"version": __version__, "model": vlm_model or "default"}, sort_keys=True)
        vlm_cache_tag = f"vlm_{hashlib.sha256(vlm_key_data.encode('utf-8')).hexdigest()[:16]}"
        cached_vlm = None if no_cache else default_cache.get(sha256, vlm_cache_tag)
        if cached_vlm is not None:
            global_evidence.extend([EvidenceItem(**item) for item in cached_vlm])
        else:
            vlm_client = VLMClient(model=vlm_model, offline=offline)
            if vlm_client.is_available():
                vlm_res = vlm_client.analyze_visual_semantics(ingest_res.preview)
                vlm_items = []
                if vlm_res:
                    if vlm_res.get("anatomy_flaws"):
                        vlm_items.append(
                            EvidenceItem(
                                name="vlm_anatomy_anomalies",
                                value=vlm_res,
                                region="global",
                                direction=ProductionMethod.AI_GENERATED.value,
                                strength=0.88,
                                explanation="VLM detected anatomical flaws (malformed hands, asymmetric eyes, or extra digits).",
                            )
                        )
                    if vlm_res.get("text_gibberish"):
                        vlm_items.append(
                            EvidenceItem(
                                name="vlm_pseudo_text_detected",
                                value=vlm_res,
                                region="global",
                                direction=ProductionMethod.AI_GENERATED.value,
                                strength=0.85,
                                explanation="VLM identified pseudo-character glyphs or corrupted background signage.",
                            )
                        )
                if vlm_items:
                    global_evidence.extend(vlm_items)
                    if not no_cache:
                        default_cache.set(sha256, vlm_cache_tag, [it.model_dump() for it in vlm_items])

    # Stage 3.D/E: Craft & Typography (fingerprinted by version, craft source code, and segmentation)
    craft_fingerprint = compute_craft_fingerprint()
    craft_meta = json.dumps({"version": __version__, "craft": craft_fingerprint, "seg": seg_fingerprint}, sort_keys=True)
    craft_cache_tag = f"craft_{hashlib.sha256(craft_meta.encode('utf-8')).hexdigest()[:16]}"
    cached_craft = None if no_cache else default_cache.get(sha256, craft_cache_tag)
    if cached_craft is not None:
        camera_info = cached_craft["camera_info"]
        lighting_info = LightingSetupInfo(**cached_craft["lighting_info"])
        palette = [PaletteColor(**p) for p in cached_craft["palette"]]
        color_grade = cached_craft["color_grade"]
        composition = CompositionInfo(**cached_craft["composition"])
    else:
        camera_info = CameraCraftEstimator().estimate(arr, seg_regions, ingest_res=ingest_res)
        lighting_info = LightingClassifier().classify(arr)
        palette = extract_dominant_palette(arr, n_colors=6)
        color_grade = analyze_color_grade(arr)
        composition = analyze_composition(arr, seg_regions)
        if not no_cache:
            default_cache.set(sha256, craft_cache_tag, {
                "camera_info": camera_info,
                "lighting_info": lighting_info.model_dump(),
                "palette": [p.model_dump() for p in palette],
                "color_grade": color_grade,
                "composition": composition.model_dump(),
            })

    typography = TypographyAnalyzer().analyze(arr, text_boxes=confirmed_text_boxes)
    layout_grid = analyze_layout_grid(arr, seg_regions)

    # Stage 4: Regional Judgment
    judge_engine = JudgmentEngine()
    region_analyses = []
    all_needs_review: List[NeedsReviewItem] = []

    # Compute regional evidence per segmented region
    regional_evidence_map: Dict[str, List[EvidenceItem]] = {}
    for r in seg_regions:
        x, y, bw, bh = r.bbox
        crop = arr[y : y + bh, x : x + bw]
        r_ev_list: List[EvidenceItem] = []
        if crop.size > 0:
            for d in detectors:
                if hasattr(d, "run_region"):
                    try:
                        r_ev_list.extend(d.run_region(crop, r.id, mask=r.mask))
                    except Exception:
                        pass
        regional_evidence_map[r.id] = r_ev_list

    for r in seg_regions:
        combined_evidence = list(global_evidence) + regional_evidence_map.get(r.id, [])
        reg_analysis, contradictions, review_items = judge_engine.judge_region(
            region_id=r.id,
            label=r.label,
            bbox=r.bbox,
            area_pct=r.area_pct,
            evidence_list=combined_evidence,
        )
        reg_analysis.palette = palette[:3]
        all_needs_review.extend(review_items)
        region_analyses.append(reg_analysis)

    # Aggregate whole-image verdict
    aggregator = VerdictAggregator()
    verdict, change_statement = aggregator.aggregate(
        regions=region_analyses,
        global_evidence=global_evidence,
        aspect_ratio=ingest_res.metadata.aspect_ratio,
        width=w,
        height=h,
        color_grade=color_grade,
    )
    dominant_method = verdict.dominant_method
    is_photo = (dominant_method == ProductionMethod.REAL_PHOTO.value)

    # Resolve camera hardware/optical forensics gated on photograph verdict
    cam_detector = CameraDetector()
    detected_cam = cam_detector.detect(
        arr=arr,
        aspect_ratio=ingest_res.metadata.aspect_ratio,
        optical_craft=camera_info,
        img=getattr(ingest_res, "rgb_image", None),
        path=getattr(ingest_res, "path", None),
        is_photograph=is_photo,
        dominant_method=dominant_method,
        redact_metadata=redact_metadata,
    )
    camera_info["detected_camera"] = detected_cam
    camera_info["camera_make"] = detected_cam.get("make")
    camera_info["camera_model"] = detected_cam.get("model")
    camera_info["camera_type"] = detected_cam.get("device_type")
    camera_info["camera_sensor"] = detected_cam.get("sensor_format")
    camera_info["camera_summary"] = detected_cam.get("summary")
    camera_info["display_name"] = detected_cam.get("display_name")

    if detected_cam.get("claimed_by_metadata"):
        cam_name = detected_cam.get("display_name", "")
        if cam_name.endswith(" (claimed by metadata)"):
            cam_name = cam_name[:-len(" (claimed by metadata)")].strip()
        if not cam_name:
            make = detected_cam.get("make", "").strip()
            model = detected_cam.get("model", "").strip()
            cam_name = model if model.lower().startswith(make.lower()) else f"{make} {model}".strip() or "Camera"
        all_needs_review.append(
            NeedsReviewItem(
                region_id="global",
                reason=f"metadata claims {cam_name}, pixels indicate {dominant_method}",
                question_for_agent=f"Examine whether {cam_name} metadata was copied/spoofed on an image produced via {dominant_method}.",
            )
        )

    # Stage 5 & 6: Reverse Engineering & Replication Planning
    prompt_builder = PromptBuilder()
    shoot_planner = PhotoShootPlanner()
    render_builder = RenderScaffoldBuilder()
    svg_builder = GraphicScaffoldBuilder()
    ui_builder = UIScaffoldBuilder()
    rep_planner = ReplicationPlanner()

    shoot_plan_data = shoot_planner.plan(
        camera_info=camera_info,
        lighting_info=lighting_info.model_dump(),
        color_info=color_grade,
        aspect_ratio=ingest_res.metadata.aspect_ratio,
        is_photograph=is_photo,
    )
    blender_script = render_builder.build_blender_script(
        scene_name=img_path.stem,
        palette_colors=[p.hex for p in palette],
    )
    svg_scaffold = svg_builder.build_svg(
        width=w,
        height=h,
        palette=palette,
        regions=region_analyses,
    )
    html_scaffold = ui_builder.build_html_css(palette=palette, regions=region_analyses)

    for reg_an in region_analyses:
        # Reverse prompt
        reg_an.reverse = prompt_builder.build(
            subject_desc=f"{reg_an.label} element",
            setting_desc="ambient environment",
            style_desc=reg_an.method,
            camera_lens=camera_info,
            lighting_info=lighting_info.model_dump(),
            color_info=color_grade,
            aspect_ratio=ingest_res.metadata.aspect_ratio,
        )
        # Replication plan
        reg_an.recreate = rep_planner.plan_region(
            region=reg_an,
            aspect_ratio=ingest_res.metadata.aspect_ratio,
        )

    # Global analysis container
    global_analysis = GlobalAnalysis(
        metadata=ingest_res.metadata.model_dump(),
        provenance={"signals_count": len([e for e in global_evidence if "exif" in e.name or "c2pa" in e.name])},
        forensics={"noise_profile": camera_info.get("vignette_falloff")},
        palette=palette,
        composition=composition.model_dump(),
        lighting=lighting_info.model_dump(),
        color_grade=color_grade,
        typography=typography.model_dump(),
        layout_grid=layout_grid,
        camera=detected_cam,
    )

    limitations = [
        "Classification is based on measurable digital forensics and metadata heuristics; not infallible proof.",
        change_statement,
        "Heavy platform compression (e.g. social media re-encoding) attenuates high-frequency noise and FFT peaks.",
        "Ethical use: Intended for structural deconstruction and recreation with authorized assets only.",
    ]
    if skipped_detectors:
        limitations.append(f"Skipped failed/uninstantiable detector(s): {', '.join(skipped_detectors)}.")
    if disabled_detectors:
        limitations.append(f"Disabled detector(s) by user request: {', '.join(disabled_detectors)}.")

    report = ReportSchema(
        image=ingest_res.metadata,
        verdict=verdict,
        regions=region_analyses,
        global_analysis=global_analysis,
        needs_review=all_needs_review,
        limitations=limitations,
    )

    # Stage 7 & 8: Export bundle
    export_assets_bundle(
        report=report,
        segment_regions=seg_regions,
        base_image=ingest_res.preview,
        out_dir=out_dir,
        blender_script=blender_script,
        svg_scaffold=svg_scaffold,
        html_scaffold=html_scaffold,
        shoot_plan_data=shoot_plan_data,
    )

    export_report_json(report, out_dir / "report.json")
    generate_report_html(report, out_dir / "report.html")

    # Cache precomputed analysis summary by image SHA-256
    default_cache.set(ingest_res.metadata.sha256, "verdict_summary", report.verdict.model_dump())

    if agent_review or all_needs_review:
        from rea_image.report.agent_review import export_agent_review_tasks
        export_agent_review_tasks(report, out_dir)

    return report


def rebuild_html_from_json(out_dir: Path) -> Path:
    """Rebuild report.html from report.json in existing directory."""
    json_path = out_dir / "report.json"
    if not json_path.exists():
        raise FileNotFoundError(f"report.json not found in {out_dir}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse through Pydantic
    report = ReportSchema(**data)
    html_path = out_dir / "report.html"
    generate_report_html(report, html_path)
    return html_path

