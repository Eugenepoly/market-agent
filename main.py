"""Unified entry point for Market Agent - HTTP and CLI interfaces."""

import os
import sys
import json
import argparse
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import functions_framework
from flask import Request, jsonify

from config import get_config
from core import Orchestrator, WorkflowContext, WorkflowStatus
from agents import ReportAgent, DeepAnalysisAgent, SocialAgent, MonitorAgent, FundFlowAgent
from agents.onchain_agent import OnchainAgent
from workflows.daily_workflow import get_daily_workflow_factory


def create_orchestrator() -> Orchestrator:
    """Create and configure the orchestrator."""
    orchestrator = Orchestrator()

    # Register agents
    orchestrator.register_agent(ReportAgent)
    orchestrator.register_agent(DeepAnalysisAgent)
    orchestrator.register_agent(SocialAgent)
    orchestrator.register_agent(MonitorAgent)
    orchestrator.register_agent(FundFlowAgent)
    orchestrator.register_agent(OnchainAgent)

    # Register workflows
    orchestrator.register_workflow("daily", get_daily_workflow_factory())

    return orchestrator


# ============== HTTP Handlers ==============

@functions_framework.http
def main_handler(request: Request):
    """Main HTTP request handler.

    Routes:
        POST /workflow/daily          - Start daily workflow
        GET  /workflow/{id}/status    - Get workflow status
        POST /workflow/{id}/approve   - Approve pending workflow
        POST /workflow/{id}/reject    - Reject pending workflow
        POST /agent/report            - Run report agent only
        POST /agent/deep-analysis     - Run deep analysis agent
        POST /agent/social            - Run social agent
        GET  /                        - Health check / legacy endpoint
    """
    path = request.path
    method = request.method

    orchestrator = create_orchestrator()

    try:
        # Health check / legacy endpoint (backwards compatible)
        if path == "/" and method == "GET":
            # Run report agent only for backwards compatibility
            context = orchestrator.run_single_agent("report_agent")
            if context.status == WorkflowStatus.COMPLETED:
                report = context.data.get("report_agent", "")
                from storage import Storage
                storage = Storage()
                result = storage.save_report(report)
                return result, 200
            else:
                return f"Error: {context.error}", 500

        # Workflow endpoints
        if path == "/workflow/daily" and method == "POST":
            data = request.get_json(silent=True) or {}
            skip_analysis = data.get("skip_analysis", False)
            topic = data.get("topic")
            collect_data = data.get("collect_data", True)
            quick_collection = data.get("quick_collection", True)

            # Update workflow factory with options
            orchestrator.register_workflow(
                "daily",
                get_daily_workflow_factory(
                    include_analysis=not skip_analysis,
                    analysis_topic=topic,
                    collect_data=collect_data,
                    quick_collection=quick_collection,
                )
            )

            context = orchestrator.run_workflow("daily")
            return jsonify(context.to_dict()), 200

        if path.startswith("/workflow/") and path.endswith("/status") and method == "GET":
            workflow_id = path.split("/")[2]
            context = orchestrator.get_status(workflow_id)
            if context:
                return jsonify(context.to_dict()), 200
            return jsonify({"error": "Workflow not found"}), 404

        if path.startswith("/workflow/") and path.endswith("/approve") and method == "POST":
            workflow_id = path.split("/")[2]
            context = orchestrator.approve(workflow_id)
            return jsonify(context.to_dict()), 200

        if path.startswith("/workflow/") and path.endswith("/reject") and method == "POST":
            workflow_id = path.split("/")[2]
            data = request.get_json(silent=True) or {}
            reason = data.get("reason")
            context = orchestrator.reject(workflow_id, reason)
            return jsonify(context.to_dict()), 200

        # Agent endpoints
        if path == "/agent/report" and method == "POST":
            context = orchestrator.run_single_agent("report_agent")
            return jsonify(context.to_dict()), 200

        if path == "/agent/deep-analysis" and method == "POST":
            data = request.get_json(silent=True) or {}
            topic = data.get("topic")
            report = data.get("report")

            # Create context with report if provided
            context = WorkflowContext()
            if report:
                context.data["report_agent"] = report

            context = orchestrator.run_single_agent(
                "deep_analysis_agent",
                context=context,
                topic=topic,
            )
            return jsonify(context.to_dict()), 200

        if path == "/agent/social" and method == "POST":
            data = request.get_json(silent=True) or {}
            report = data.get("report")
            analysis = data.get("analysis")

            # Create context with inputs
            context = WorkflowContext()
            if report:
                context.data["report_agent"] = report
            if analysis:
                context.data["deep_analysis_agent"] = {"analysis": analysis}

            context = orchestrator.run_single_agent("social_agent", context=context)
            return jsonify(context.to_dict()), 200

        if path == "/agent/monitor" and method == "POST":
            data = request.get_json(silent=True) or {}
            quick = data.get("quick", False)

            monitor = MonitorAgent()
            if quick:
                result = monitor.run_quick_check()
                return jsonify(result), 200
            else:
                context = WorkflowContext()
                result = monitor.run(context)
                return jsonify(result.to_dict()), 200

        if path == "/agent/fundflow" and method == "POST":
            data = request.get_json(silent=True) or {}
            quick = data.get("quick", False)

            fundflow = FundFlowAgent()
            if quick:
                result = fundflow.run_quick_check()
                return jsonify(result), 200
            else:
                context = WorkflowContext()
                result = fundflow.run(context)
                return jsonify(result.to_dict()), 200

        if path == "/agent/onchain" and method == "POST":
            data = request.get_json(silent=True) or {}
            quick = data.get("quick", False)

            onchain = OnchainAgent()
            result = onchain.run(quick=quick)
            return jsonify({
                "success": result.success,
                "output": result.output,
                "error": result.error,
            }), 200

        # List workflows
        if path == "/workflows" and method == "GET":
            workflows = orchestrator.list_workflows()
            return jsonify(workflows), 200

        return jsonify({"error": "Not found"}), 404

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============== CLI Interface ==============

def cli_workflow_daily(args):
    """Run daily workflow via CLI."""
    orchestrator = create_orchestrator()

    # Configure workflow
    orchestrator.register_workflow(
        "daily",
        get_daily_workflow_factory(
            include_analysis=not args.skip_analysis,
            analysis_topic=args.topic,
            collect_data=not args.skip_collection,
            quick_collection=not args.full_collection,
        )
    )

    print("Starting daily workflow...")
    if not args.skip_collection:
        print("Step 1: Collecting data (VIP social, fund flow, onchain)...")
    context = orchestrator.run_workflow("daily")

    if context.status == WorkflowStatus.WAITING_APPROVAL:
        print(f"\nWorkflow paused for approval (ID: {context.workflow_id})")
        print("\n" + "=" * 50)
        print("DRAFT FOR REVIEW:")
        print("=" * 50)

        social_data = context.data.get("social_agent", {})
        draft = social_data.get("draft", str(social_data))
        print(draft)

        print("\n" + "=" * 50)

        # Interactive approval in local mode
        if get_config().is_local_mode:
            response = input("\nApprove this draft? (y/n): ").strip().lower()
            if response == "y":
                context = orchestrator.approve(context.workflow_id)
                print(f"\nApproved! Draft saved to: {get_config().approved_drafts_dir}")
            else:
                reason = input("Rejection reason (optional): ").strip()
                context = orchestrator.reject(context.workflow_id, reason or None)
                print("\nRejected.")
        else:
            print(f"\nUse 'python main.py workflow approve {context.workflow_id}' to approve")
            print(f"Or 'python main.py workflow reject {context.workflow_id}' to reject")

    elif context.status == WorkflowStatus.COMPLETED:
        print(f"\nWorkflow completed successfully (ID: {context.workflow_id})")
    else:
        print(f"\nWorkflow failed: {context.error}")
        sys.exit(1)


def cli_workflow_status(args):
    """Get workflow status via CLI."""
    orchestrator = create_orchestrator()
    context = orchestrator.get_status(args.workflow_id)

    if context:
        print(json.dumps(context.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Workflow '{args.workflow_id}' not found")
        sys.exit(1)


def cli_workflow_approve(args):
    """Approve workflow via CLI."""
    orchestrator = create_orchestrator()
    try:
        context = orchestrator.approve(args.workflow_id)
        print(f"Workflow approved. Draft saved to: {get_config().approved_drafts_dir}")
        print(json.dumps(context.to_dict(), indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cli_workflow_reject(args):
    """Reject workflow via CLI."""
    orchestrator = create_orchestrator()
    try:
        context = orchestrator.reject(args.workflow_id, args.reason)
        print("Workflow rejected.")
        print(json.dumps(context.to_dict(), indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cli_workflow_list(args):
    """List all workflows via CLI."""
    orchestrator = create_orchestrator()
    workflows = orchestrator.list_workflows()

    if not workflows:
        print("No workflows found.")
        return

    for wf in workflows:
        status_emoji = {
            "pending": "⏳",
            "running": "🔄",
            "waiting_approval": "⏸️",
            "completed": "✅",
            "failed": "❌",
            "rejected": "🚫",
        }.get(wf["status"], "❓")

        print(f"{status_emoji} {wf['workflow_id'][:8]}... | {wf['workflow_name']} | {wf['status']} | {wf['created_at']}")


def cli_agent_report(args):
    """Run report agent via CLI."""
    orchestrator = create_orchestrator()
    print("Running report agent...")

    context = orchestrator.run_single_agent("report_agent")

    if context.status == WorkflowStatus.COMPLETED:
        report = context.data.get("report_agent", "")
        print("\n" + "=" * 50)
        print(report)
        print("=" * 50)

        from storage import Storage
        storage = Storage()
        path = storage.save_report(report)
        print(f"\nReport saved to: {path}")
    else:
        print(f"Error: {context.error}")
        sys.exit(1)


def cli_agent_analysis(args):
    """Run deep analysis agent via CLI."""
    orchestrator = create_orchestrator()

    # Need report first
    if not args.report_file:
        print("Error: --report-file is required for deep analysis")
        sys.exit(1)

    with open(args.report_file, "r", encoding="utf-8") as f:
        report = f.read()

    context = WorkflowContext()
    context.data["report_agent"] = report

    print(f"Running deep analysis agent (topic: {args.topic or 'auto'})...")
    context = orchestrator.run_single_agent(
        "deep_analysis_agent",
        context=context,
        topic=args.topic,
    )

    if context.status == WorkflowStatus.COMPLETED:
        analysis_data = context.data.get("deep_analysis_agent", {})
        analysis = analysis_data.get("analysis", str(analysis_data))
        print("\n" + "=" * 50)
        print(analysis)
        print("=" * 50)

        from storage import Storage
        storage = Storage()
        path = storage.save_analysis(analysis)
        print(f"\nAnalysis saved to: {path}")
    else:
        print(f"Error: {context.error}")
        sys.exit(1)


def cli_agent_social(args):
    """Run social agent via CLI."""
    orchestrator = create_orchestrator()

    if not args.report_file:
        print("Error: --report-file is required for social agent")
        sys.exit(1)

    with open(args.report_file, "r", encoding="utf-8") as f:
        report = f.read()

    context = WorkflowContext()
    context.data["report_agent"] = report

    if args.analysis_file:
        with open(args.analysis_file, "r", encoding="utf-8") as f:
            analysis = f.read()
        context.data["deep_analysis_agent"] = {"analysis": analysis}

    print("Running social agent...")
    context = orchestrator.run_single_agent("social_agent", context=context)

    if context.status == WorkflowStatus.COMPLETED:
        social_data = context.data.get("social_agent", {})
        draft = social_data.get("draft", str(social_data))
        print("\n" + "=" * 50)
        print("DRAFT:")
        print("=" * 50)
        print(draft)
        print("=" * 50)

        # Save draft to pending_social_content
        from storage import Storage
        storage = Storage()
        path = storage.save_pending_draft(draft, context.workflow_id)
        print(f"\nDraft saved to: {path}")
        print("Copy and post manually to X.")
    else:
        print(f"Error: {context.error}")
        sys.exit(1)


def _cleanup_monitor_files(directory: str, prefix: str, max_files: int = 3) -> None:
    """Remove old monitor files, keeping only the most recent ones."""
    if not os.path.exists(directory):
        return

    files = [f for f in os.listdir(directory) if f.startswith(prefix)]

    if len(files) <= max_files:
        return

    files.sort()
    files_to_delete = files[:-max_files]

    for filename in files_to_delete:
        filepath = os.path.join(directory, filename)
        try:
            os.remove(filepath)
        except Exception:
            pass


def cli_agent_fundflow(args):
    """Run fund flow agent via CLI."""
    print("Running fund flow agent...")

    fundflow = FundFlowAgent()

    if args.quick:
        # Quick check without LLM analysis
        result = fundflow.run_quick_check()

        print(f"\n{'='*50}")
        print("FUND FLOW QUICK CHECK")
        print(f"{'='*50}")

        # Market
        market = result.get("market", {})
        if market:
            print("\n📊 Market Summary:")
            for symbol, info in market.items():
                if isinstance(info, dict) and info.get("price"):
                    change = info.get("change_percent", 0)
                    sign = "+" if change and change > 0 else ""
                    print(f"  {info.get('name', symbol)}: {info['price']} ({sign}{change:.2f}%)")

        # Institutional
        institutional = result.get("institutional", {})
        if institutional:
            print("\n🏦 Institutional Activity:")
            for symbol, data in institutional.items():
                inst_trans = data.get('inst_trans', 'N/A')
                insider_trans = data.get('insider_trans', 'N/A')
                short_float = data.get('short_float', 'N/A')
                print(f"  {symbol}: 机构{inst_trans}, 内部人{insider_trans}, 做空{short_float}")

        # Options
        options = result.get("options", {})
        if options:
            print("\n📈 Put/Call Ratios:")
            for symbol, data in options.items():
                pc = data.get('pc_ratio', 'N/A')
                iv = data.get('avg_iv')
                iv_str = f", IV={iv*100:.1f}%" if iv else ""
                print(f"  {symbol}: P/C={pc}{iv_str}")

        # Crypto
        crypto = result.get("crypto", {})
        if crypto:
            fng = crypto.get('fear_greed')
            fng_label = crypto.get('fear_greed_label', '')
            if fng:
                print(f"\n₿ Crypto Fear & Greed: {fng} ({fng_label})")

            funding = crypto.get("funding_rates", {})
            if funding:
                print("  Funding Rates:")
                for symbol, rate in funding.items():
                    if rate:
                        print(f"    {symbol}: {rate*100:.4f}%")

        # Save result
        import json
        monitor_dir = "./data/fund_flows"
        os.makedirs(monitor_dir, exist_ok=True)
        from datetime import datetime
        filename = f"{monitor_dir}/quick_check_{datetime.now().strftime('%Y%m%d_%H')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nResult saved to: {filename}")

        _cleanup_monitor_files(monitor_dir, "quick_check_", max_files=3)

    else:
        # Full analysis with LLM
        context = WorkflowContext()
        result = fundflow.run(context)

        if result.success:
            output = result.output
            print("\n" + "=" * 50)
            print(output.get("analysis", "No analysis generated"))
            print("=" * 50)

            # Save analysis
            monitor_dir = "./data/fund_flows"
            os.makedirs(monitor_dir, exist_ok=True)
            from datetime import datetime
            filename = f"{monitor_dir}/analysis_{datetime.now().strftime('%Y%m%d_%H')}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(output.get("analysis", ""))
            print(f"\nAnalysis saved to: {filename}")

            _cleanup_monitor_files(monitor_dir, "analysis_", max_files=3)
        else:
            print(f"Error: {result.error}")
            sys.exit(1)


def cli_agent_monitor(args):
    """Run monitor agent via CLI."""
    print("Running VIP monitor agent...")

    monitor = MonitorAgent()

    if args.quick:
        # Quick check without LLM analysis
        result = monitor.run_quick_check()
        print(f"\nPosts collected: {result['posts_collected']}")
        print(f"Sources: {', '.join(result['sources']) if result['sources'] else 'None'}")

        if result['high_priority_alerts']:
            print("\n🔴 HIGH PRIORITY ALERTS:")
            for alert in result['high_priority_alerts']:
                post = alert['post']
                keywords = [kw[1] for kw in alert['matched_keywords']]
                print(f"  @{post['handle']}: {post['content'][:100]}...")
                print(f"    Keywords: {', '.join(keywords)}")
        elif result['alerts']:
            print(f"\n⚠️ {len(result['alerts'])} keyword alerts detected")
        else:
            print("\n✅ No alerts")

        # Save result (hourly, keep max 3)
        import json
        monitor_dir = "./data/monitor"
        os.makedirs(monitor_dir, exist_ok=True)
        from datetime import datetime
        filename = f"{monitor_dir}/quick_check_{datetime.now().strftime('%Y%m%d_%H')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nResult saved to: {filename}")

        # Cleanup old files
        _cleanup_monitor_files(monitor_dir, "quick_check_", max_files=3)

    else:
        # Full analysis with LLM
        context = WorkflowContext()
        result = monitor.run(context)

        if result.success:
            output = result.output
            print("\n" + "=" * 50)
            print(output.get("analysis", "No analysis generated"))
            print("=" * 50)
            print(f"\nPosts collected: {output.get('posts_collected', 0)}")
            print(f"Keyword alerts: {output.get('keyword_alerts_count', 0)}")

            # Save analysis (hourly, keep max 3)
            monitor_dir = "./data/monitor"
            os.makedirs(monitor_dir, exist_ok=True)
            from datetime import datetime
            filename = f"{monitor_dir}/analysis_{datetime.now().strftime('%Y%m%d_%H')}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(output.get("analysis", ""))
            print(f"\nAnalysis saved to: {filename}")

            # Cleanup old files
            _cleanup_monitor_files(monitor_dir, "analysis_", max_files=3)
        else:
            print(f"Error: {result.error}")
            sys.exit(1)


def cli_agent_onchain(args):
    """Run on-chain monitor agent via CLI."""
    print("Running on-chain monitor agent...")

    onchain = OnchainAgent()
    result = onchain.run(quick=args.quick)

    if result.success:
        print("\n" + "=" * 50)
        print(result.output)
        print("=" * 50)

        if result.error:
            print(f"\n⚠️ Some errors occurred: {result.error}")
    else:
        print(f"Error: {result.error}")
        sys.exit(1)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Market Agent - Multi-agent market analysis system"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Workflow commands
    workflow_parser = subparsers.add_parser("workflow", help="Workflow operations")
    workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_command")

    # workflow daily
    daily_parser = workflow_subparsers.add_parser("daily", help="Run daily workflow")
    daily_parser.add_argument("--skip-analysis", action="store_true", help="Skip deep analysis step")
    daily_parser.add_argument("--topic", type=str, help="Specific topic for deep analysis")
    daily_parser.add_argument("--skip-collection", action="store_true", help="Skip data collection step")
    daily_parser.add_argument("--full-collection", action="store_true", help="Run full data collection with LLM analysis")

    # workflow status
    status_parser = workflow_subparsers.add_parser("status", help="Get workflow status")
    status_parser.add_argument("workflow_id", help="Workflow ID")

    # workflow approve
    approve_parser = workflow_subparsers.add_parser("approve", help="Approve workflow")
    approve_parser.add_argument("workflow_id", help="Workflow ID")

    # workflow reject
    reject_parser = workflow_subparsers.add_parser("reject", help="Reject workflow")
    reject_parser.add_argument("workflow_id", help="Workflow ID")
    reject_parser.add_argument("--reason", type=str, help="Rejection reason")

    # workflow list
    workflow_subparsers.add_parser("list", help="List all workflows")

    # Agent commands
    agent_parser = subparsers.add_parser("agent", help="Run individual agents")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command")

    # agent report
    agent_subparsers.add_parser("report", help="Run report agent")

    # agent analysis
    analysis_parser = agent_subparsers.add_parser("analysis", help="Run deep analysis agent")
    analysis_parser.add_argument("--report-file", required=True, help="Path to report file")
    analysis_parser.add_argument("--topic", type=str, help="Specific topic to analyze")

    # agent social
    social_parser = agent_subparsers.add_parser("social", help="Run social agent")
    social_parser.add_argument("--report-file", required=True, help="Path to report file")
    social_parser.add_argument("--analysis-file", type=str, help="Path to analysis file (optional)")

    # agent monitor
    monitor_parser = agent_subparsers.add_parser("monitor", help="Run VIP monitor agent")
    monitor_parser.add_argument("--quick", action="store_true", help="Quick check without LLM analysis")

    # agent fundflow
    fundflow_parser = agent_subparsers.add_parser("fundflow", help="Run fund flow agent")
    fundflow_parser.add_argument("--quick", action="store_true", help="Quick check without LLM analysis")

    # agent onchain
    onchain_parser = agent_subparsers.add_parser("onchain", help="Run on-chain monitor agent")
    onchain_parser.add_argument("--quick", action="store_true", help="Quick check without LLM analysis")

    args = parser.parse_args()

    # Set local mode for CLI
    os.environ["RUN_LOCAL"] = "true"

    if args.command == "workflow":
        if args.workflow_command == "daily":
            cli_workflow_daily(args)
        elif args.workflow_command == "status":
            cli_workflow_status(args)
        elif args.workflow_command == "approve":
            cli_workflow_approve(args)
        elif args.workflow_command == "reject":
            cli_workflow_reject(args)
        elif args.workflow_command == "list":
            cli_workflow_list(args)
        else:
            workflow_parser.print_help()
    elif args.command == "agent":
        if args.agent_command == "report":
            cli_agent_report(args)
        elif args.agent_command == "analysis":
            cli_agent_analysis(args)
        elif args.agent_command == "social":
            cli_agent_social(args)
        elif args.agent_command == "monitor":
            cli_agent_monitor(args)
        elif args.agent_command == "fundflow":
            cli_agent_fundflow(args)
        elif args.agent_command == "onchain":
            cli_agent_onchain(args)
        else:
            agent_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
