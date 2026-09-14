"""AURA CLI entry point (Typer app).

Commands are added incrementally as each domain engine lands:
``validate`` (Iteration 1), ``analyze`` (Iteration 2), ``score``
(Iteration 3), ``failures`` (Iteration 4), ``report``/``adr`` (Iteration 5),
``aws inventory``/``terraform inspect``/``validate-deployed`` (Phase 2),
``gate``/``observe``/``chaos`` (Phase 3).
"""

from __future__ import annotations

from pathlib import Path

import typer

from aura import __version__
from aura.architecture.generator import generate_candidates
from aura.cli.output import to_json
from aura.domain.enums import EligibilityStatus
from aura.domain.models import Workload
from aura.errors import AuraError
from aura.evaluation.engine import evaluate_all, select_recommendation
from aura.failure.simulator import simulate_all
from aura.providers.conformance import compare_candidate_to_observed, compare_terraform_to_observed
from aura.providers.terraform import load_terraform_plan
from aura.reporting.adr import generate_adrs
from aura.reporting.context import build_context
from aura.reporting.markdown import render_report
from aura.reporting.terraform_codegen import build_terraform_context, generate_terraform_files
from aura.requirements.loader import load_workload_document
from aura.requirements.normalizer import NormalizedRequirements, normalize
from aura.requirements.validator import validate_workload

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="AURA — architecture decision, validation, and reliability-analysis platform.",
)
aws_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Read-only AWS inspection (Phase 2).")
terraform_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Terraform plan inspection (Phase 2).")
chaos_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Controlled failure experiments (Phase 3, docs-sanctioned first tier only).",
)
app.add_typer(aws_app, name="aws")
app.add_typer(terraform_app, name="terraform")
app.add_typer(chaos_app, name="chaos")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aura {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the AURA version and exit.",
    ),
) -> None:
    """AURA — architecture decision, validation, and reliability-analysis platform."""


def load_normalized_workload(
    workload_path: Path,
) -> tuple[dict, Workload, NormalizedRequirements]:
    """Shared load -> validate -> normalize pipeline used by every CLI command."""

    document = load_workload_document(workload_path)
    workload = validate_workload(document)
    normalized = normalize(workload, raw_document=document)
    return document, workload, normalized


def fail(exc: AuraError) -> None:
    typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
    for detail in getattr(exc, "details", None) or []:
        typer.secho(f"  - {detail}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1) from exc


@app.command()
def validate(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
) -> None:
    """Validate a workload document and print the normalized requirements."""

    try:
        _, _, normalized = load_normalized_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    typer.echo(to_json(normalized.model_dump(mode="json")))

    if normalized.conflicts:
        typer.secho(
            f"\n{len(normalized.conflicts)} conflict(s) detected — see 'conflicts' above.",
            fg=typer.colors.YELLOW,
            err=True,
        )


@app.command()
def analyze(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
) -> None:
    """Generate candidate architectures for a workload."""

    try:
        _, _, normalized = load_normalized_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    candidates = generate_candidates(normalized)
    typer.echo(to_json([c.model_dump(mode="json") for c in candidates]))
    typer.secho(
        f"\n{len(candidates)} candidate(s) generated.",
        fg=typer.colors.GREEN,
        err=True,
    )


@app.command()
def failures(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
) -> None:
    """Simulate the eight failure scenarios against every candidate architecture."""

    try:
        _, _, normalized = load_normalized_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    candidates = generate_candidates(normalized)
    reports = simulate_all(candidates, normalized)
    typer.echo(to_json({cid: r.model_dump(mode="json") for cid, r in reports.items()}))

    for candidate_id, report in reports.items():
        marker = "✓" if report.survives_region_failure else "✗"
        typer.secho(
            f"{marker} {candidate_id}: worst blast radius={report.worst_blast_radius.value}, "
            f"AZ survives={report.survives_az_failure}, region survives={report.survives_region_failure}",
            err=True,
        )


@app.command()
def score(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
) -> None:
    """Score every candidate architecture: eligibility, dimensions, weighted score, confidence."""

    try:
        _, _, normalized = load_normalized_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    candidates = generate_candidates(normalized)
    scores = evaluate_all(candidates, normalized)
    typer.echo(to_json([s.model_dump(mode="json") for s in scores]))

    recommendation = select_recommendation(scores)
    typer.secho("", err=True)
    for candidate_score in scores:
        marker = "★" if recommendation and candidate_score.candidate_id == recommendation.candidate_id else " "
        if candidate_score.eligibility == EligibilityStatus.ELIGIBLE:
            typer.secho(
                f"{marker} {candidate_score.candidate_id}: ELIGIBLE score="
                f"{candidate_score.weighted_score} confidence={candidate_score.confidence}",
                fg=typer.colors.GREEN,
                err=True,
            )
        else:
            typer.secho(
                f"{marker} {candidate_score.candidate_id}: INELIGIBLE — "
                f"{'; '.join(candidate_score.ineligibility_reasons)}",
                fg=typer.colors.RED,
                err=True,
            )


def _evaluate_workload(workload_path: Path):
    document, workload, normalized = load_normalized_workload(workload_path)
    candidates = generate_candidates(normalized)
    scores = evaluate_all(candidates, normalized)
    return workload, normalized, candidates, scores


@app.command()
def report(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
    output: Path = typer.Option(..., "--output", "-o", help="Directory to write report.md and report.json into."),
) -> None:
    """Generate the full architecture report (Markdown + JSON)."""

    try:
        workload, normalized, candidates, scores = _evaluate_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    ctx = build_context(workload, normalized, candidates, scores)
    output.mkdir(parents=True, exist_ok=True)

    report_md = render_report(ctx)
    (output / "report.md").write_text(report_md, encoding="utf-8")

    report_json = to_json(
        {
            "workload": workload.model_dump(mode="json"),
            "normalized": normalized.model_dump(mode="json"),
            "candidates": [c.model_dump(mode="json") for c in candidates],
            "scores": [s.model_dump(mode="json") for s in scores],
            "recommendation": ctx.recommendation.candidate_id if ctx.recommendation else None,
        }
    )
    (output / "report.json").write_text(report_json, encoding="utf-8")

    typer.secho(f"wrote {output / 'report.md'}", fg=typer.colors.GREEN, err=True)
    typer.secho(f"wrote {output / 'report.json'}", fg=typer.colors.GREEN, err=True)


@app.command()
def adr(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
    output: Path = typer.Option(..., "--output", "-o", help="Directory to write ADR files into."),
) -> None:
    """Generate ADRs for the recommended architecture's key decisions."""

    try:
        workload, normalized, candidates, scores = _evaluate_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    ctx = build_context(workload, normalized, candidates, scores)
    documents = generate_adrs(ctx)

    if not documents:
        typer.secho(
            "no ADRs generated: no candidate was eligible for recommendation.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)

    output.mkdir(parents=True, exist_ok=True)
    for filename, content in documents.items():
        (output / filename).write_text(content, encoding="utf-8")
        typer.secho(f"wrote {output / filename}", fg=typer.colors.GREEN, err=True)


@aws_app.command("inventory")
def aws_inventory(
    region: str = typer.Option(..., "--region", help="AWS region to inspect."),
) -> None:
    """Read-only discovery of compute/database/load-balancer/cache resources in a region."""

    from aura.providers.aws import Boto3AwsProvider, collect_inventory

    try:
        provider = Boto3AwsProvider()
        inventory = collect_inventory(provider, region)
    except AuraError as exc:
        fail(exc)
        return

    typer.echo(to_json(inventory.model_dump(mode="json")))


@terraform_app.command("inspect")
def terraform_inspect(
    plan_path: Path = typer.Argument(..., help="Path to `terraform show -json` output."),
) -> None:
    """Parse a Terraform plan JSON file into its declared resources. Never runs Terraform."""

    try:
        desired = load_terraform_plan(plan_path)
    except AuraError as exc:
        fail(exc)
        return

    typer.echo(to_json(desired.model_dump(mode="json")))
    typer.secho(f"\n{len(desired.resources)} resource(s) declared.", fg=typer.colors.GREEN, err=True)


@terraform_app.command("generate")
def terraform_generate(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
    output_dir: Path = typer.Option(
        ..., "--output-dir", "-o", help="Directory to write providers.tf/variables.tf/main.tf/outputs.tf into."
    ),
    candidate_id: str | None = typer.Option(
        None,
        "--candidate",
        help="Generate for this specific pattern id instead of the recommendation, e.g. single-region-multi-az.",
    ),
) -> None:
    """Render real Terraform from a candidate's actual topology — closes the loop between
    'AURA recommends X' and 'the infrastructure matches X'. Regenerate this after any workload
    change instead of hand-editing; never touches an existing deployed environment's state."""

    try:
        _, normalized, candidates, scores = _evaluate_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    if candidate_id:
        candidate = next((c for c in candidates if c.id == candidate_id), None)
        if candidate is None:
            typer.secho(
                f"error: no candidate '{candidate_id}'. Choices: {', '.join(c.id for c in candidates)}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
    else:
        recommendation = select_recommendation(scores)
        if recommendation is None:
            typer.secho(
                "error: no eligible candidate to generate from. Pass --candidate to force a "
                "specific (possibly ineligible) one.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        candidate = next(c for c in candidates if c.id == recommendation.candidate_id)

    files = generate_terraform_files(candidate, normalized)
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (output_dir / filename).write_text(content, encoding="utf-8")

    typer.secho(
        f"generated {len(files)} file(s) in {output_dir} for candidate '{candidate.id}' ({candidate.name}).",
        fg=typer.colors.GREEN,
        err=True,
    )

    ctx = build_terraform_context(candidate, normalized)
    total_tasks = ctx["primary_desired_count"] + ctx["secondary_desired_count"]
    if total_tasks > 20:
        typer.secho(
            f"note: {ctx['primary_desired_count']} + {ctx['secondary_desired_count']} tasks is what "
            f"{ctx['peak_rps']:.0f} peak RPS actually needs — real, but not demo-sized. Override before "
            f"applying: terraform apply -var primary_desired_count=3 -var secondary_desired_count=2",
            fg=typer.colors.YELLOW,
            err=True,
        )

    typer.secho("next: cd there and run `terraform init && terraform validate && terraform plan`.", err=True)


@terraform_app.command("drift")
def terraform_drift(
    plan_path: Path = typer.Argument(..., help="Path to `terraform show -json` output."),
    region: str = typer.Option(..., "--region", help="AWS region to inspect."),
) -> None:
    """Compare a Terraform plan's declared resources against real, observed AWS state."""

    from aura.providers.aws import Boto3AwsProvider, collect_inventory

    try:
        desired = load_terraform_plan(plan_path)
        provider = Boto3AwsProvider()
        inventory = collect_inventory(provider, region)
    except AuraError as exc:
        fail(exc)
        return

    report = compare_terraform_to_observed(desired, inventory)
    typer.echo(to_json(report.model_dump(mode="json")))
    for check in report.checks:
        marker = "✓" if check.status.value == "PASS" else "✗"
        typer.secho(
            f"{marker} {check.check_id}: expected={check.expected} observed={check.observed} "
            f"status={check.status.value}",
            fg=typer.colors.GREEN if check.status.value == "PASS" else typer.colors.RED,
            err=True,
        )
    if not report.passed:
        raise typer.Exit(code=1)


@app.command(name="validate-deployed")
def validate_deployed(
    workload: Path = typer.Option(..., "--workload", help="Path to a workload YAML file."),
    region: str = typer.Option(..., "--region", help="AWS region to inspect."),
) -> None:
    """Compare AURA's recommended architecture against real, observed AWS state."""

    from aura.providers.aws import Boto3AwsProvider, collect_inventory

    try:
        workload_obj, normalized_reqs, candidates, scores = _evaluate_workload(workload)
    except AuraError as exc:
        fail(exc)
        return

    recommendation = select_recommendation(scores)
    if recommendation is None:
        typer.secho(
            "no eligible candidate to validate against: every candidate is INELIGIBLE.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        provider = Boto3AwsProvider()
        inventory = collect_inventory(provider, region)
    except AuraError as exc:
        fail(exc)
        return

    recommended_candidate = next(c for c in candidates if c.id == recommendation.candidate_id)
    report = compare_candidate_to_observed(recommended_candidate, normalized_reqs, inventory)
    typer.echo(to_json(report.model_dump(mode="json")))

    for check in report.checks:
        marker = "✓" if check.status.value == "PASS" else "✗"
        typer.secho(
            f"{marker} {check.check_id}: expected={check.expected} observed={check.observed} "
            f"status={check.status.value}",
            fg=typer.colors.GREEN if check.status.value == "PASS" else typer.colors.RED,
            err=True,
        )
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def gate(
    workload_path: Path = typer.Argument(..., help="Path to a workload YAML file."),
    min_confidence: float = typer.Option(
        0.0, "--min-confidence", help="Fail if the recommendation's confidence is below this (0-1)."
    ),
    baseline: Path | None = typer.Option(
        None, "--baseline", help="Path to a JSON file with a prior {'recommendation_id': ...} to diff against."
    ),
) -> None:
    """CI architecture gate (docs/IMPLEMENTATION_PHASES.md Phase 3): exit non-zero on a
    mandatory-constraint failure (no eligible candidate) or low-confidence recommendation.
    A changed recommendation vs. --baseline is reported but does not fail the build — an
    architecture change can be intentional."""

    try:
        _, _, candidates, scores = _evaluate_workload(workload_path)
    except AuraError as exc:
        fail(exc)
        return

    recommendation = select_recommendation(scores)
    eligible_count = sum(1 for s in scores if s.eligibility == EligibilityStatus.ELIGIBLE)

    typer.echo(f"candidates: {len(candidates)} generated, {eligible_count} eligible")

    if recommendation is None:
        typer.secho(
            "GATE FAILED: no eligible candidate — every candidate violates a mandatory constraint.",
            fg=typer.colors.RED,
            err=True,
        )
        for s in scores:
            if s.ineligibility_reasons:
                typer.secho(f"  {s.candidate_id}: {'; '.join(s.ineligibility_reasons)}", err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"recommendation: {recommendation.candidate_id} "
        f"(score={recommendation.weighted_score}, confidence={recommendation.confidence})"
    )

    if baseline is not None and baseline.exists():
        import json as _json

        previous = _json.loads(baseline.read_text(encoding="utf-8")).get("recommendation_id")
        if previous and previous != recommendation.candidate_id:
            typer.secho(
                f"NOTE: recommendation changed from '{previous}' to '{recommendation.candidate_id}' "
                "— confirm this is intentional.",
                fg=typer.colors.YELLOW,
                err=True,
            )

    if recommendation.confidence < min_confidence:
        typer.secho(
            f"GATE FAILED: recommendation confidence {recommendation.confidence} is below "
            f"--min-confidence {min_confidence}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    typer.secho("GATE PASSED", fg=typer.colors.GREEN, err=True)


@app.command()
def observe(
    namespace: str = typer.Option(..., "--namespace", help="CloudWatch namespace, e.g. AWS/RDS."),
    metric_name: str = typer.Option(..., "--metric", help="CloudWatch metric name, e.g. ReplicaLag."),
    dimension: list[str] = typer.Option(
        ..., "--dimension", help="Dimension as Name=Value. Repeatable for multiple dimensions."
    ),
    region: str = typer.Option(..., "--region", help="AWS region the metric lives in."),
    statistic: str = typer.Option("Average", "--statistic", help="CloudWatch statistic."),
    minutes: int = typer.Option(15, "--minutes", help="Lookback window."),
) -> None:
    """Pull a real CloudWatch metric — the one place AURA can produce MEASURED
    (not MODELLED) evidence. Example: verify the actual cross-region replica
    lag against the RPO the failure model assumed.

    \b
    aura observe --namespace AWS/RDS --metric ReplicaLag --region ap-southeast-1 \\
        --dimension DBInstanceIdentifier=aura-demo-secondary
    """

    from aura.providers.observability import Boto3ObservabilityProvider

    dimensions: dict[str, str] = {}
    for item in dimension:
        if "=" not in item:
            typer.secho(f"error: --dimension must be Name=Value, got: {item}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        key, _, value = item.partition("=")
        dimensions[key] = value

    try:
        provider = Boto3ObservabilityProvider()
        series = provider.get_metric(
            namespace=namespace,
            metric_name=metric_name,
            dimensions=dimensions,
            statistic=statistic,
            minutes=minutes,
            region=region,
        )
    except AuraError as exc:
        fail(exc)
        return

    typer.echo(to_json(series.model_dump(mode="json")))
    if series.latest is None:
        typer.secho(
            "no datapoints in this window (metric may be inactive, or the window too short).",
            fg=typer.colors.YELLOW,
            err=True,
        )
    else:
        typer.secho(f"latest: {series.latest}", fg=typer.colors.GREEN, err=True)


@chaos_app.command("terminate-task")
def chaos_terminate_task(
    cluster: str = typer.Option(..., "--cluster", help="ECS cluster name."),
    region: str = typer.Option(..., "--region"),
    confirm: bool = typer.Option(
        False, "--confirm", help="Required: acknowledges this stops a real, running ECS task."
    ),
) -> None:
    """Docs-sanctioned experiment #1: terminate one disposable task and let the
    orchestrator replace it. This is a REAL, mutating AWS call."""

    if not confirm:
        typer.secho(
            "refusing to run: pass --confirm to acknowledge this stops a real running ECS task.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    from aura.providers.chaos import Boto3ChaosProvider

    try:
        provider = Boto3ChaosProvider()
        result = provider.stop_one_task(cluster=cluster, region=region)
    except AuraError as exc:
        fail(exc)
        return

    typer.echo(to_json(result.model_dump(mode="json")))
    typer.secho(
        "stopped. watch the service's task count to confirm the orchestrator replaces it.",
        fg=typer.colors.GREEN,
        err=True,
    )


@chaos_app.command("remove-target")
def chaos_remove_target(
    target_group_arn: str = typer.Option(..., "--target-group-arn"),
    region: str = typer.Option(..., "--region"),
    confirm: bool = typer.Option(
        False, "--confirm", help="Required: acknowledges this deregisters a real, healthy target."
    ),
) -> None:
    """Docs-sanctioned experiment #2: remove one healthy target from an ALB
    target group. This is a REAL, mutating AWS call."""

    if not confirm:
        typer.secho(
            "refusing to run: pass --confirm to acknowledge this deregisters a real healthy target.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    from aura.providers.chaos import Boto3ChaosProvider

    try:
        provider = Boto3ChaosProvider()
        result = provider.deregister_one_target(target_group_arn=target_group_arn, region=region)
    except AuraError as exc:
        fail(exc)
        return

    typer.echo(to_json(result.model_dump(mode="json")))


@chaos_app.command("synthetic-traffic")
def chaos_synthetic_traffic(
    url: str = typer.Argument(..., help="URL to hit repeatedly, e.g. an ALB DNS name."),
    duration: float = typer.Option(30.0, "--duration", help="Seconds to run."),
    rps: float = typer.Option(2.0, "--rps", help="Requests per second."),
) -> None:
    """Docs-sanctioned experiment #3: generate synthetic traffic. Plain HTTP
    GETs — non-destructive, needs no AWS permissions, not gated by --confirm."""

    from aura.providers.chaos import generate_synthetic_traffic

    typer.secho(f"sending ~{rps} req/s to {url} for {duration}s...", err=True)
    result = generate_synthetic_traffic(url, duration_seconds=duration, requests_per_second=rps)
    typer.echo(to_json(result.model_dump(mode="json")))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on source changes (development only)."),
) -> None:
    """Run the AURA JSON API that backs the web UI (see web/, `npm run dev`)."""

    import uvicorn

    typer.secho(f"AURA API: http://{host}:{port}  (docs: http://{host}:{port}/docs)", fg=typer.colors.GREEN, err=True)
    typer.secho("Start the UI separately: cd web && npm run dev", fg=typer.colors.GREEN, err=True)
    uvicorn.run("aura.web.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
