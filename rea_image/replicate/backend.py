"""Pluggable generation backend with dry-run and confirmation safeguards."""

from typing import Any, Dict
from rich.console import Console
from rich.panel import Panel

console = Console()


class GenerationBackend:
    """Orchestrates image recreation calls with strict dry-run and confirmation guards."""

    def execute_recreation(
        self,
        prompt: str,
        negative_prompt: str = "",
        model_name: str = "FLUX.1 [dev]",
        aspect_ratio: str = "1:1",
        est_cost: str = "$0.025",
        dry_run: bool = True,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Preview or execute an image generation task.
        
        Always performs a safe dry-run unless dry_run is False AND confirmed is True.
        """
        summary_text = (
            f"[bold]Model:[/bold] {model_name}\n"
            f"[bold]Aspect Ratio:[/bold] {aspect_ratio}\n"
            f"[bold]Estimated Cost:[/bold] {est_cost}\n\n"
            f"[bold cyan]Prompt:[/bold cyan]\n\"{prompt}\"\n\n"
            f"[bold magenta]Negative Prompt:[/bold magenta]\n\"{negative_prompt}\""
        )

        if dry_run or not confirmed:
            console.print(
                Panel(
                    summary_text,
                    title="[bold yellow]Recreation Simulation (Dry Run)[/bold yellow]",
                    subtitle="Run with --confirm to proceed with live generation",
                    expand=False,
                )
            )
            return {
                "status": "simulated",
                "dry_run": True,
                "model": model_name,
                "prompt": prompt,
                "est_cost": est_cost,
                "message": "Dry run complete. No network requests or billable API calls made.",
            }

        # If user explicitly confirms with --confirm
        console.print(f"[bold green]Executing confirmed recreation with {model_name}...[/bold green]")
        # Network integration hook (opt-in API call)
        return {
            "status": "ready_for_dispatch",
            "dry_run": False,
            "model": model_name,
            "prompt": prompt,
            "est_cost": est_cost,
            "message": "Generation task confirmed and ready for dispatch.",
        }

