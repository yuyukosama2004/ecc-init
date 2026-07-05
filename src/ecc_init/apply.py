from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from . import __version__
from .core.models import InstallPlan
from .core.receipt import ReceiptStore
from .core.transaction import Transaction
from .errors import ConfigError
from .packs import load_registry
from .packs.gsd_bridge import build_gsd_config
from .packs.installer import ComponentInstaller
from .paths import AppPaths
from .sources import BundledProvider, GitHubArchiveProvider, SourceLock, SourceLockStore
from .util import now_iso
from .workflows import GsdInstallOptions, GsdWorkflowAdapter


@dataclass(frozen=True)
class ApplyOptions:
    dry_run: bool = True
    yes: bool = False
    expected_project_root: Path | None = None
    skip_gsd_check: bool = False
    sync_gsd: bool | None = None
    offline: bool = False
    install_gsd: bool = False
    runtime: str = "claude"
    scope: str = "global"
    version: str = "1.6.1"


@dataclass
class ApplyReport:
    project_root: Path
    dry_run: bool
    applied: bool
    status: str
    plan: InstallPlan
    operation_id: str | None = None
    backup_id: str | None = None
    files_planned: list[dict[str, Any]] = field(default_factory=list)
    files_written: list[dict[str, Any]] = field(default_factory=list)
    sources_locked: list[dict[str, Any]] = field(default_factory=list)
    config_report: dict[str, Any] | None = None
    workflow_status: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "dry_run": self.dry_run,
            "applied": self.applied,
            "status": self.status,
            "operation_id": self.operation_id,
            "backup_id": self.backup_id,
            "install_plan": self.plan.to_dict(),
            "files_planned": list(self.files_planned),
            "files_written": list(self.files_written),
            "sources_locked": list(self.sources_locked),
            "config_report": self.config_report,
            "workflow_status": self.workflow_status,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def load_apply_plan(path: Path) -> InstallPlan:
    return InstallPlan.from_json(path.read_text(encoding="utf-8"))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _workflow_result_to_dict(result) -> dict[str, Any]:
    return {
        "workflow_id": result.workflow_id,
        "status": result.status,
        "ok": result.ok,
        "commands": [
            {"args": list(command.args), "description": command.description, "dry_run": command.dry_run}
            for command in result.commands
        ],
        "checks": [
            {
                "check_id": check.check_id,
                "ok": check.ok,
                "message": check.message,
                "detail": check.detail,
            }
            for check in result.checks
        ],
        "logs": [
            {
                "args": list(log.args),
                "returncode": log.returncode,
                "stdout": log.stdout,
                "stderr": log.stderr,
            }
            for log in result.logs
        ],
        "warnings": list(result.warnings),
    }


def validate_apply_plan(plan: InstallPlan, *, expected_project_root: Path | None = None) -> tuple[list[str], list[str]]:
    registry = load_registry()
    warnings: list[str] = []
    errors: list[str] = []
    expected_root = (expected_project_root or Path.cwd()).expanduser().resolve()
    project_root = plan.project_root.expanduser().resolve()
    paths = AppPaths.build(project_root)

    if project_root != expected_root:
        errors.append(f"plan project_root {project_root} does not match current project root {expected_root}")
    if plan.workflow not in registry.workflows:
        errors.append(f"unknown workflow in plan: {plan.workflow}")

    unknown_packs = sorted(set(plan.packs) - set(registry.packs))
    if unknown_packs:
        errors.append(f"unknown pack in plan: {', '.join(unknown_packs)}")

    source_ids = set(registry.sources)
    component_ids = set(registry.components)
    operation_ids: set[str] = set()

    def add_operation_id(operation_id: str) -> None:
        if operation_id in operation_ids:
            errors.append(f"duplicate operation id: {operation_id}")
        operation_ids.add(operation_id)

    component_targets = {component.target_path.expanduser().resolve() for component in plan.resolved_components}
    for component in plan.resolved_components:
        if component.component_id not in component_ids:
            errors.append(f"unknown component in plan: {component.component_id}")
        if component.source_id not in source_ids:
            errors.append(f"unknown source in component {component.component_id}: {component.source_id}")
        if component.target_scope == "project" and not _is_within(component.target_path, project_root):
            errors.append(f"component target escapes project root: {component.target_path}")
        if component.target_scope == "global" and not _is_within(component.target_path, paths.claude_home):
            errors.append(f"component target escapes Claude home: {component.target_path}")

    for operation in [*plan.file_operations, *plan.external_operations, *plan.config_operations]:
        add_operation_id(operation.operation_id)

    for operation in plan.file_operations:
        if operation.source_id not in source_ids:
            errors.append(f"unknown source in file operation {operation.operation_id}: {operation.source_id}")
        if operation.target_scope == "project" and not _is_within(operation.path, project_root):
            errors.append(f"file operation escapes project root: {operation.path}")
        if operation.target_scope == "global" and not _is_within(operation.path, paths.claude_home):
            errors.append(f"file operation escapes Claude home: {operation.path}")
        if operation.path.expanduser().resolve() not in component_targets:
            warnings.append(f"file operation has no matching resolved component: {operation.operation_id}")

    if any(operation.target_scope == "global" for operation in plan.file_operations):
        warnings.append("Plan includes global file operations; apply will not write them in this batch.")
    return warnings, errors


def apply_install_plan(plan: InstallPlan, options: ApplyOptions | None = None) -> ApplyReport:
    options = options or ApplyOptions()
    warnings, errors = validate_apply_plan(plan, expected_project_root=options.expected_project_root)
    paths = AppPaths.build(plan.project_root)
    registry = load_registry()
    workflow_status: dict[str, Any] | None = None
    config_report: dict[str, Any] | None = None

    if not options.yes and not options.dry_run:
        options = ApplyOptions(
            dry_run=True,
            yes=False,
            expected_project_root=options.expected_project_root,
            skip_gsd_check=options.skip_gsd_check,
            sync_gsd=options.sync_gsd,
            offline=options.offline,
            install_gsd=options.install_gsd,
            runtime=options.runtime,
            scope=options.scope,
            version=options.version,
        )
        warnings.append("No --yes supplied; apply is reported as a dry-run preview.")

    if plan.workflow == "gsd":
        adapter = GsdWorkflowAdapter()
        gsd_options = GsdInstallOptions(
            runtime=options.runtime,
            scope=options.scope,
            version=options.version,
            yes=options.yes,
            dry_run=options.dry_run,
        )
        if options.install_gsd:
            result = adapter.install(paths, gsd_options)
        elif options.skip_gsd_check:
            result = None
        else:
            result = adapter.status(paths, runtime=options.runtime, scope=options.scope)
        if result is not None:
            workflow_status = _workflow_result_to_dict(result)
            if result.status in {"not_installed", "blocked_environment"}:
                warnings.append(f"GSD Core status is {result.status}; apply will not install GSD without --install-gsd.")
            if options.install_gsd and not options.dry_run and not result.ok:
                errors.append(f"GSD install did not complete: {result.status}")

    sync_requested = options.sync_gsd
    config_path = paths.project_root / ".planning" / "config.json"
    if sync_requested is None:
        sync_requested = config_path.exists()
    if sync_requested:
        report = build_gsd_config(paths.project_root, packs=plan.packs, dry_run=True)
        config_report = report.to_dict()
        warnings.extend(report.warnings)
    elif not config_path.exists():
        warnings.append("GSD config is not initialized; apply will not create .planning/config.json.")

    files_planned = [operation.to_dict() for operation in plan.file_operations]
    sources_locked = [
        {"source_id": source_id, "status": "planned"}
        for source_id in sorted({component.source_id for component in plan.resolved_components})
    ]

    status = "dry_run" if options.dry_run else "blocked"
    if errors:
        status = "blocked"
    elif not options.dry_run:
        transaction = Transaction(
            paths.backups_dir,
            paths.project_root,
            receipt_store=ReceiptStore(paths.operations_dir),
            workflow_id=plan.workflow,
        )
        try:
            state = _load_project_state(paths, plan)
            install_report = ComponentInstaller(registry).install(
                plan,
                transaction=transaction,
                state=state,
                cache_dir=paths.cache_dir,
                offline=options.offline,
            )
            warnings.extend(install_report.warnings)
            errors.extend(install_report.errors)
            if errors:
                rollback = transaction.rollback()
                return ApplyReport(
                    project_root=paths.project_root,
                    dry_run=False,
                    applied=False,
                    status="failed",
                    plan=plan,
                    operation_id=transaction.operation_id,
                    backup_id=rollback.backup_id,
                    files_planned=files_planned,
                    files_written=[item.to_dict() for item in install_report.files_written],
                    sources_locked=sources_locked,
                    config_report=config_report,
                    workflow_status=workflow_status,
                    warnings=warnings,
                    errors=errors,
                )

            locks = _resolve_source_locks(
                registry,
                plan,
                paths=paths,
                offline=options.offline,
                source_ids={item.source_id for item in install_report.files_written},
            )
            if locks:
                _write_source_lock(paths, transaction, locks)
            _write_project_state(paths, transaction, plan, install_report.files_written, locks, workflow_status)
            receipt = transaction.finish(
                result="success",
                packs=[{"pack_id": pack_id, "version": registry.packs[pack_id].version} for pack_id in plan.packs],
                sources=[lock.to_dict() for lock in locks.values()],
            )
            return ApplyReport(
                project_root=paths.project_root,
                dry_run=False,
                applied=True,
                status="applied",
                plan=plan,
                operation_id=receipt.operation_id,
                backup_id=receipt.backup_id,
                files_planned=files_planned,
                files_written=[item.to_dict() for item in install_report.files_written],
                sources_locked=[lock.to_dict() for lock in locks.values()],
                config_report=config_report,
                workflow_status=workflow_status,
                warnings=warnings,
                errors=[],
            )
        except Exception as exc:
            rollback = transaction.rollback()
            errors.append(str(exc))
            return ApplyReport(
                project_root=paths.project_root,
                dry_run=False,
                applied=False,
                status="failed",
                plan=plan,
                operation_id=transaction.operation_id,
                backup_id=rollback.backup_id,
                files_planned=files_planned,
                files_written=[],
                sources_locked=sources_locked,
                config_report=config_report,
                workflow_status=workflow_status,
                warnings=warnings,
                errors=errors,
            )

    return ApplyReport(
        project_root=paths.project_root,
        dry_run=options.dry_run,
        applied=False,
        status=status,
        plan=plan,
        files_planned=files_planned,
        files_written=[],
        sources_locked=sources_locked,
        config_report=config_report,
        workflow_status=workflow_status,
        warnings=warnings,
        errors=errors,
    )


def _load_project_state(paths: AppPaths, plan: InstallPlan) -> dict[str, Any]:
    try:
        payload = json.loads(paths.project_state.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "schema_version": 2,
            "tool_version": __version__,
            "project_root": str(paths.project_root),
            "detected_stacks": [],
            "detection_evidence": {},
            "workflow": {"id": plan.workflow, "scope": plan.workflow_scope, "installed": False, "verified": False},
            "profiles": [],
            "packs": {},
            "managed_files": {},
            "source_locks": {},
            "pending_gsd_config": {},
        }
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"unable to read project state {paths.project_state}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"project state must be a JSON object: {paths.project_state}")
    schema = payload.get("schema_version", payload.get("version"))
    if schema not in {2, None}:
        raise ConfigError("project state is legacy schema; run `ecc-init migrate --dry-run` before apply")
    payload.setdefault("managed_files", {})
    payload.setdefault("packs", {})
    payload.setdefault("source_locks", {})
    return payload


def _resolve_source_locks(
    registry,
    plan: InstallPlan,
    *,
    paths: AppPaths,
    offline: bool,
    source_ids: set[str] | None = None,
) -> dict[str, SourceLock]:
    locks: dict[str, SourceLock] = {}
    bundled_provider = BundledProvider()
    github_provider = GitHubArchiveProvider()
    selected_source_ids = source_ids if source_ids is not None else {component.source_id for component in plan.resolved_components}
    for source_id in sorted(selected_source_ids):
        source = registry.sources[source_id]
        if source.kind == "bundled":
            locks[source_id] = bundled_provider.resolve(source).lock
            continue
        if source.kind == "github_archive":
            locks[source_id] = github_provider.resolve(source, paths.cache_dir, offline=offline).lock
            continue
        if any(component.source_id == source_id and component.required for component in plan.resolved_components):
            raise ConfigError(f"unsupported required source kind during apply: {source_id} ({source.kind})")
    return locks


def _write_source_lock(paths: AppPaths, transaction: Transaction, locks: dict[str, SourceLock]) -> None:
    existing = SourceLockStore(paths.source_lock).load_all()
    existing.update(locks)
    payload = {
        "schema_version": 1,
        "sources": {source_id: lock.to_dict() for source_id, lock in sorted(existing.items())},
    }
    transaction.write_text(paths.source_lock, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", owner="source-lock")


def _write_project_state(
    paths: AppPaths,
    transaction: Transaction,
    plan: InstallPlan,
    files_written: list[Any],
    locks: dict[str, SourceLock],
    workflow_status: dict[str, Any] | None,
) -> None:
    state = _load_project_state(paths, plan)
    managed_files = state.setdefault("managed_files", {})
    for item in files_written:
        managed_files[str(item.path.resolve())] = {
            "source_id": item.source_id,
            "component_id": item.component_id,
            "owners": [item.owner],
            "sha256": item.sha256,
            "base_hash": item.sha256,
            "content_version": item.sha256,
        }
    state.update(
        {
            "schema_version": 2,
            "tool_version": __version__,
            "project_root": str(paths.project_root),
            "workflow": {
                "id": plan.workflow,
                "scope": plan.workflow_scope,
                "installed": bool(workflow_status and workflow_status.get("status") in {"installed_verified", "installed_unverified"}),
                "verified": bool(workflow_status and workflow_status.get("status") == "installed_verified"),
            },
            "packs": {pack_id: {"version": 1} for pack_id in plan.packs},
            "source_locks": {source_id: lock.to_dict() for source_id, lock in locks.items()},
            "last_operation_id": transaction.operation_id,
            "last_initialized_at": now_iso(),
        }
    )
    transaction.write_text(
        paths.project_state,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        owner="project-state",
    )
