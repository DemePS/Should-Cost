"""Local terminal runner for the should-cost workflow — no SharePoint, no App Service.

    python -m should_cost.cli \
        --material-id 0T0001 \
        --material-folder ./local_input/0T0001 \
        --ppe-file ./local_input/HAGER_PPE_2025.xlsx \
        --output-dir ./local_output

Reads the PPE spreadsheet and the material-folder documents from local disk instead of
Microsoft Graph, builds the Job/JobUnits directly (bypassing Step 0's Graph calls), and
drives the real workflow/graph.py LangGraph orchestrator with ``skip_upload=True`` — Step 7 never
calls Graph; the generated Excel files are copied into --output-dir instead of uploaded.

Still talks to Azure AI Foundry for the three structured calls and the research agent's
web search — this removes the SharePoint/App-Service dependency, not the model/network
dependency. Set the usual AZURE_AI_FOUNDRY_* / SEARCH_PROVIDER env vars (a local .env is
read automatically by should_cost.config.Settings). SHAREPOINT_* vars are still required
by Settings' schema but are never read by this code path — any placeholder value works.

A needs_input pause is handled interactively: the question is printed, your answer is
read from stdin, and the job resumes — looping until it reaches done or failed.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from should_cost.config import get_settings
from should_cost.data.documents import parse_document
from should_cost.data.spend import load_ppe_dataframe, lookup_spend
from should_cost.models.common import MatchType, SpendLookupResult, SupplierRow, SupplierType
from should_cost.models.job import DiscoveryDocument, Job, JobStatus, JobUnit
from should_cost.state.store import InMemoryJobStateStore
from should_cost.tools.foundry_credentials import build_foundry_credential
from should_cost.workflow.graph import answer_job, run_job


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--material-id", required=True, help="SAP material ID, e.g. 0T0001")
    parser.add_argument(
        "--material-folder", type=Path, default=None,
        help="Directory of drawings/BOM/RFQ/spec files for this material (optional)"
    )
    parser.add_argument("--ppe-file", type=Path, required=True, help="Local HAGER PPE spreadsheet (.xlsx or .xlsb)")
    parser.add_argument("--output-dir", type=Path, default=Path("./should_cost_output"))
    parser.add_argument("--language", default="en", choices=["en", "fr", "de"])
    return parser.parse_args(argv)


def _read_local_documents(folder: Path | None) -> list[DiscoveryDocument]:
    if folder is None:
        return []
    if not folder.exists():
        print(f"Warning: --material-folder {folder} does not exist — proceeding with no documents.")
        return []
    docs: list[DiscoveryDocument] = []
    for path in sorted(folder.iterdir()):
        if path.is_dir():
            continue
        try:
            parsed = parse_document(str(path))
        except ValueError:
            continue  # unsupported extension — not a document to extract from
        docs.append(DiscoveryDocument(filename=path.name, text=parsed.text))
        print(f"  parsed {path.name}")
    return docs


def _prompt_manual_override(material_id: str) -> SupplierRow:
    print(
        f"Material ID {material_id!r} was not found in the PPE file (exact or prefix match).\n"
        "Enter Annual Volume, Annual Spend, Current Average Price manually, comma-separated "
        "(e.g. 500000,25000,0.05):"
    )
    while True:
        raw = input("> ").strip()
        try:
            volume_s, spend_s, price_s = (part.strip() for part in raw.split(","))
            return SupplierRow(
                supplier_name="MANUAL OVERRIDE",
                hager_entity="unknown",
                unit_of_measure="EA",
                annual_volume=float(volume_s),
                annual_spend=float(spend_s),
                current_avg_price=float(price_s),
                supplier_type=SupplierType.UNKNOWN,
                is_manual_override=True,
            )
        except ValueError:
            print("Could not parse that as 'volume,spend,price' — try again.")


def _copy_outputs(job: Job, output_dir: Path) -> None:
    for unit in job.units:
        for f in unit.files:
            if f.local_path and Path(f.local_path).exists():
                dest = output_dir / f.name
                shutil.copy2(f.local_path, dest)
                print(f"  wrote {dest}")


def _print_summary(job: Job) -> None:
    print(f"\n=== Job {job.job_id} — {job.status.value} ===")
    if job.status == JobStatus.FAILED:
        print(f"Failure reason: {job.failure_reason}")
        return
    for unit in job.units:
        if unit.is_rollup or unit.cost_build is None:
            continue
        cb = unit.cost_build
        sanity = unit.sanity_gate.overall_status.value if unit.sanity_gate else "n/a"
        print(
            f"\n{unit.label}:\n"
            f"  Current price:  €{cb.get('current_price_eur', 0):.4f}\n"
            f"  Should cost:    €{cb.get('should_cost_eur', 0):.4f}\n"
            f"  Impact/unit:    €{cb.get('impact_eur', 0):.4f}\n"
            f"  Sanity gate:    {sanity}"
        )
        if unit.insights:
            print(f"  Supplier question: {unit.insights.highest_information_gain_question}")
    if job.cross_supplier_table:
        print("\nCross-supplier comparison:")
        for row in job.cross_supplier_table:
            print(f"  {row}")


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    credential = build_foundry_credential(settings)
    store = InMemoryJobStateStore()

    print(f"Reading PPE file: {args.ppe_file}")
    ppe = load_ppe_dataframe(str(args.ppe_file), args.ppe_file.name)
    spend_lookup = lookup_spend(ppe, args.material_id)

    if spend_lookup.match_type == MatchType.NOT_FOUND:
        manual_supplier = _prompt_manual_override(args.material_id)
        spend_lookup = SpendLookupResult(
            match_type=MatchType.MANUAL_OVERRIDE, base_id=args.material_id, suppliers=[manual_supplier]
        )
    elif spend_lookup.plausibility_note and "may represent a different material" in spend_lookup.plausibility_note:
        print(spend_lookup.plausibility_note)
        if input("Proceed with these variants anyway? [y/N] > ").strip().lower() != "y":
            return 1

    print(f"Found {len(spend_lookup.suppliers)} supplier row(s):")
    for s in spend_lookup.suppliers:
        print(
            f"  - {s.supplier_name} ({s.country or 'unknown'}) — {s.supplier_type.value} — "
            f"vol {s.annual_volume:,.0f}, price €{s.current_avg_price:.4f}"
        )
    if len(spend_lookup.suppliers) > 1:
        print("Pitfall P2: one model will be built per supplier above — never blended.")

    print(f"Reading material folder: {args.material_folder}")
    documents = _read_local_documents(args.material_folder)
    print(f"  {len(documents)} document(s) parsed.")

    job = Job(material_id=args.material_id, language=args.language, requested_by="local-cli")
    job.spend_lookup = spend_lookup
    job.discovery_documents = documents
    job.units = [JobUnit(label=s.supplier_name, supplier=s) for s in spend_lookup.suppliers]
    await store.save(job)

    print("\nRunning workflow (this talks to Azure AI Foundry for every model call)…")
    await run_job(job, store=store, settings=settings, credential=credential, skip_upload=True)
    job = await store.load(job.job_id)

    while job.status == JobStatus.NEEDS_INPUT and job.pending_question is not None:
        print(f"\n[needs_input] {job.pending_question.reason}")
        print(job.pending_question.question)
        if job.pending_question.context:
            print(f"  ({job.pending_question.context})")
        answer = input("> ").strip()
        await answer_job(job, answer, store=store, settings=settings, credential=credential, skip_upload=True)
        job = await store.load(job.job_id)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _copy_outputs(job, args.output_dir)
    (args.output_dir / "job.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nFull job state written to {args.output_dir / 'job.json'}")

    _print_summary(job)
    return 0 if job.status == JobStatus.DONE else 1


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
