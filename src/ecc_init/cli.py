from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .app import doctor, initialize_project, project_status, rollback


COMMANDS = {"init", "status", "update", "doctor", "rollback"}


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

    diagnose = sub.add_parser("doctor", help="检查 Python、Git、目录权限和内置资源")
    diagnose.add_argument("path", nargs="?", default=".")

    restore = sub.add_parser("rollback", help="从最近一次备份恢复")
    restore.add_argument("path", nargs="?", default=".")
    restore.add_argument("--backup", dest="backup_id", help="指定备份 ID；默认使用最新备份")
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(_normalize_argv(list(sys.argv[1:] if argv is None else argv)))
    command = args.command or "init"
    try:
        if command in {"init", "update"}:
            report = initialize_project(Path(args.path), offline=args.offline, no_sync=args.no_sync)
            _print_report(report)
            return 2 if report.conflicts else 0
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
            return 0
        if command == "doctor":
            failed = False
            for label, ok, detail in doctor(Path(args.path)):
                print(f"[{'PASS' if ok else 'WARN'}] {label}: {detail}")
                failed = failed or not ok
            return 1 if failed else 0
        if command == "rollback":
            backup_id, count = rollback(Path(args.path), args.backup_id)
            print(f"已从备份 {backup_id} 恢复 {count} 项。")
            return 0
    except Exception as exc:  # CLI 顶层必须给出清楚错误，不输出冗长堆栈。
        print(f"ecc-init 执行失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
