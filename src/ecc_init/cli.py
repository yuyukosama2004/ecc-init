from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .app import doctor, initialize_project, project_status, rollback
from .packs import build_registry_install_plan, load_registry
from .packs.gsd_bridge import sync_gsd_config
from .sources import verify_registry_sources
from .util import write_text_atomic
from .workflows import GsdWorkflowAdapter


COMMANDS = {"init", "plan", "packs", "sources", "workflow", "sync-gsd", "status", "update", "doctor", "rollback"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecc-init",
        description="为 Claude Code 初始化轻量全局规则、通用 Skill 与项目技术栈配置。",
    )
    parser.add_argument("--version", action="version", version=f"ecc-init {__version__}")
    sub = parser.add_subparsers(dest="command")

    for name in ("init", "update"):
        command = sub.add_parser(name, help="初始化或同步当前项目")
        command.add_argument("path", nargs="?", default=".", help="项目目录，默认当前目录")
        command.add_argument("--offline", action="store_true", help="不访问网络，使用缓存或内置模板")
        command.add_argument("--no-sync", action="store_true", help="完全跳过 ECC 上游同步")

    status = sub.add_parser("status", help="显示当前项目识别结果和安装状态")
    status.add_argument("path", nargs="?", default=".")

    plan = sub.add_parser("plan", help="预览声明式安装计划，不修改项目文件")
    plan.add_argument("path", nargs="?", default=".")
    plan.add_argument("--profile", default="default", help="声明式 profile，默认 default")
    plan.add_argument("--pack", action="append", default=[], help="额外启用 Pack，可重复")
    plan.add_argument("--without-pack", action="append", default=[], help="排除 Pack，可重复")
    plan.add_argument("--workflow", help="覆盖 profile 声明的 workflow")
    plan.add_argument("--json", action="store_true", help="以 JSON 输出 InstallPlan")
    plan.add_argument("--output", help="将 JSON InstallPlan 写入指定文件")

    packs = sub.add_parser("packs", help="查看声明式 Pack Registry")
    packs_sub = packs.add_subparsers(dest="packs_command", required=True)
    packs_list = packs_sub.add_parser("list", help="列出 Pack")
    packs_list.add_argument("--json", action="store_true", help="以 JSON 输出")
    packs_show = packs_sub.add_parser("show", help="显示 Pack 详情")
    packs_show.add_argument("pack")
    packs_show.add_argument("--json", action="store_true", help="以 JSON 输出")

    sources = sub.add_parser("sources", help="查看和校验来源声明")
    sources_sub = sources.add_subparsers(dest="sources_command", required=True)
    sources_list = sources_sub.add_parser("list", help="列出来源")
    sources_list.add_argument("--json", action="store_true", help="以 JSON 输出")
    sources_verify = sources_sub.add_parser("verify", help="校验来源声明")
    sources_verify.add_argument("--json", action="store_true", help="以 JSON 输出")

    workflow = sub.add_parser("workflow", help="查看 Workflow Adapter 状态")
    workflow_sub = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_status = workflow_sub.add_parser("status", help="显示 GSD adapter 检查结果")
    workflow_status.add_argument("path", nargs="?", default=".")
    workflow_status.add_argument("--json", action="store_true", help="以 JSON 输出")

    sync_gsd = sub.add_parser("sync-gsd", help="合并 Pack 生成的 GSD 配置，不覆盖用户显式配置")
    sync_gsd.add_argument("path", nargs="?", default=".")
    sync_gsd.add_argument("--profile", default="default", help="Agent policy/profile，默认 default")
    sync_gsd.add_argument("--pack", action="append", default=[], help="仅同步指定 Pack，可重复")
    sync_gsd.add_argument("--dry-run", action="store_true", help="只输出预览，不写入 config")
    sync_gsd.add_argument("--json", action="store_true", help="以 JSON 输出")

    diagnose = sub.add_parser("doctor", help="检查 Python、Git、目录权限和内置资源")
    diagnose.add_argument("path", nargs="?", default=".")

    restore = sub.add_parser("rollback", help="从最近一次备份恢复")
    restore.add_argument("path", nargs="?", default=".")
    restore.add_argument("--backup", dest="backup_id", help="指定备份 ID；默认使用最新备份")
    restore.add_argument("--operation-id", help="按 operation receipt 中记录的 backup 恢复")
    restore.add_argument("--receipt", help="按 receipt 文件中记录的 backup 恢复")
    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["init"]
    if argv[0] in COMMANDS or argv[0] in {"--version", "-h", "--help"}:
        return argv
    # 支持在任意目录直接执行 `ecc-init D:\\project`。
    return ["init", *argv]


def _print_report(report) -> None:
    print(f"项目：{report.project_root}")
    print("识别技术栈：" + ("、".join(report.detection.stacks) if report.detection.stacks else "未识别"))
    if report.upstream_ref:
        print(f"ECC 上游 ref：{report.upstream_ref}")

    counts: dict[str, int] = {}
    for result in report.results:
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status in {"conflict", "preserved"}:
            print(f"[需处理] {result.path}: {result.message}")
    print("文件结果：" + "，".join(f"{key}={value}" for key, value in sorted(counts.items())))
    if report.backup_id:
        print(f"备份：{report.backup_id}")
    for warning in report.warnings:
        print(f"[提示] {warning}")
    if report.conflicts:
        print("存在冲突对比文件；当前使用的仍是你的本地版本。")


def _print_plan_summary(plan) -> None:
    print(f"项目：{plan.project_root}")
    print(f"工作流：{plan.workflow} ({plan.workflow_scope})")
    print("能力包：" + ("、".join(plan.packs) if plan.packs else "无"))
    print(f"文件操作：{len(plan.file_operations)}")
    print(f"外部命令：{len(plan.external_operations)}")
    for warning in plan.warnings:
        print(f"[提示] {warning}")


def _print_pack_list(json_output: bool) -> None:
    registry = load_registry()
    items = [pack.to_dict() for pack in registry.packs.values()]
    if json_output:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    for pack in registry.packs.values():
        print(f"{pack.pack_id}\tv{pack.version}\t{pack.description}")


def _print_pack_show(pack_id: str, json_output: bool) -> int:
    registry = load_registry()
    pack = registry.packs.get(pack_id)
    if pack is None:
        print(f"未知 Pack：{pack_id}", file=sys.stderr)
        return 1
    payload = pack.to_dict()
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"Pack：{pack.pack_id}")
    print(f"版本：{pack.version}")
    print(f"说明：{pack.description}")
    print("组件：" + ("、".join(pack.components) if pack.components else "无"))
    print("依赖：" + ("、".join(pack.requires) if pack.requires else "无"))
    print("冲突：" + ("、".join(pack.conflicts) if pack.conflicts else "无"))
    print("技术栈条件：" + ("、".join(pack.stack_conditions) if pack.stack_conditions else "无"))
    return 0


def _print_sources_list(json_output: bool) -> None:
    registry = load_registry()
    items = [source.to_dict() for source in registry.sources.values()]
    if json_output:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    for source in registry.sources.values():
        license_label = source.license_id or "unknown"
        print(f"{source.source_id}\t{source.kind}\t{license_label}\t{source.repository or source.package or ''}")


def _print_sources_verify(json_output: bool) -> int:
    registry = load_registry()
    checks = verify_registry_sources(registry)
    if json_output:
        print(json.dumps([check.to_dict() for check in checks], ensure_ascii=False, indent=2))
    else:
        for check in checks:
            print(f"[{'PASS' if check.ok else 'FAIL'}] {check.check_id}: {check.message} {check.detail}".rstrip())
    return 0 if all(check.ok for check in checks) else 1


def _print_workflow_status(path: Path, json_output: bool) -> int:
    from .paths import AppPaths

    result = GsdWorkflowAdapter().verify(AppPaths.build(path))
    checks = [check.__dict__ for check in result.checks]
    if json_output:
        print(json.dumps({"workflow": result.workflow_id, "status": result.status, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print(f"Workflow：{result.workflow_id}")
        print(f"状态：{result.status}")
        for check in result.checks:
            print(f"[{'PASS' if check.ok else 'WARN'}] {check.check_id}: {check.message} {check.detail}".rstrip())
    return 0 if result.ok else 1


def _print_sync_gsd(args) -> int:
    report = sync_gsd_config(
        Path(args.path),
        profile_id=args.profile,
        packs=args.pack or None,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"GSD config：{report.config_path}")
        print(f"初始化：" + ("是" if report.initialized else "否"))
        print(f"变更：" + ("是" if report.changed else "否"))
        print("模式：" + ("dry-run" if args.dry_run else "apply"))
        for warning in report.warnings:
            print(f"[提示] {warning}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(_normalize_argv(list(sys.argv[1:] if argv is None else argv)))
    command = args.command or "init"
    try:
        if command in {"init", "update"}:
            report = initialize_project(Path(args.path), offline=args.offline, no_sync=args.no_sync)
            _print_report(report)
            return 2 if report.conflicts else 0
        if command == "plan":
            plan = build_registry_install_plan(
                Path(args.path),
                profile_id=args.profile,
                include_packs=args.pack,
                exclude_packs=args.without_pack,
                workflow=args.workflow,
            )
            content = plan.to_json()
            if args.output:
                write_text_atomic(Path(args.output), content + "\n")
            if args.json:
                print(content)
            else:
                _print_plan_summary(plan)
                if args.output:
                    print(f"计划文件：{Path(args.output)}")
            return 0
        if command == "packs":
            if args.packs_command == "list":
                _print_pack_list(args.json)
                return 0
            if args.packs_command == "show":
                return _print_pack_show(args.pack, args.json)
        if command == "sources":
            if args.sources_command == "list":
                _print_sources_list(args.json)
                return 0
            if args.sources_command == "verify":
                return _print_sources_verify(args.json)
        if command == "workflow":
            if args.workflow_command == "status":
                return _print_workflow_status(Path(args.path), args.json)
        if command == "sync-gsd":
            return _print_sync_gsd(args)
        if command == "status":
            status = project_status(Path(args.path))
            print(f"项目：{status['project_root']}")
            print("识别技术栈：" + ("、".join(status["detected_stacks"]) or "未识别"))
            print("全局 CLAUDE.md：" + ("已存在" if status["global_claude_md"] else "未创建"))
            print("全局 Skill：" + ("、".join(status["global_skills"]) or "无"))
            print("项目 Skill：" + ("、".join(status["project_skills"]) or "无"))
            print("代码导读完成：" + ("是" if status["code_tour_completed"] else "否"))
            print(f"上游 ref：{status['upstream_ref'] or '未知'}")
            print(f"上次初始化：{status['last_initialized_at'] or '从未'}")
            print(f"备份数量：{status['backup_count']}")
            if status["conflicts"]:
                print("冲突文件：")
                for item in status["conflicts"]:
                    print(f"- {item}")
            if status["modified_managed_files"]:
                print("本地修改的受管文件：")
                for item in status["modified_managed_files"]:
                    print(f"- {item}")
            return 0
        if command == "doctor":
            failed = False
            for label, ok, detail in doctor(Path(args.path)):
                print(f"[{'PASS' if ok else 'WARN'}] {label}: {detail}")
                failed = failed or not ok
            return 1 if failed else 0
        if command == "rollback":
            backup_id, count = rollback(
                Path(args.path),
                args.backup_id,
                args.operation_id,
                Path(args.receipt) if args.receipt else None,
            )
            print(f"已从备份 {backup_id} 恢复 {count} 项。")
            return 0
    except Exception as exc:  # CLI 顶层必须给出清楚错误，不输出冗长堆栈。
        print(f"ecc-init 执行失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
