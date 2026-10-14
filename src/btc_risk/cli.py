import argparse
import sys

from btc_risk.config import get_settings
from btc_risk.format import format_assessment, format_report


def _require_key(settings) -> None:
    if not settings.openai_api_key:
        sys.exit(
            "OPENAI_API_KEY is not set (put it in .env). `assess` and `sanctions-update` work without it."
        )


def cmd_sanctions_update(args) -> None:
    from btc_risk.deps import load_sanctions

    s = load_sanctions(get_settings(), refresh=True)
    print(f"OFAC SDN list refreshed: {len(s)} listed Bitcoin addresses")


def cmd_assess(args) -> None:
    from btc_risk.chain.risk import assess_address
    from btc_risk.deps import build_chain_source, load_sanctions

    settings = get_settings()
    a = assess_address(
        build_chain_source(settings), load_sanctions(settings), args.address, max_depth=args.depth
    )
    print(a.model_dump_json(indent=2) if args.json else format_assessment(a))


def cmd_ingest(args) -> None:
    from btc_risk.deps import build_vector_store
    from btc_risk.ingest.pipeline import ingest

    settings = get_settings()
    _require_key(settings)
    print(f"ingested {ingest(args.sources, build_vector_store(settings))} chunks")


def cmd_ask(args) -> None:
    from btc_risk.agents.qa import answer_question
    from btc_risk.deps import build_chat_model, build_vector_store, langfuse_config

    settings = get_settings()
    _require_key(settings)
    ans = answer_question(
        build_vector_store(settings),
        build_chat_model(settings),
        args.question,
        config=langfuse_config(),
    )
    print(ans.answer, "\n\nsources:", ", ".join(ans.chunk_ids))


def cmd_investigate(args) -> None:
    from btc_risk.agents.graph import investigate
    from btc_risk.agents.single import investigate_single
    from btc_risk.deps import build_chat_model, build_deps, langfuse_config

    settings = get_settings()
    _require_key(settings)
    deps = build_deps(settings)
    run = investigate_single if args.single else investigate
    report = run(deps, build_chat_model(settings), args.address, config=langfuse_config())
    print(report.model_dump_json(indent=2) if args.json else format_report(report))


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("btc_risk.api.app:app", host=args.host, port=args.port)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="btc-risk", description="Bitcoin wallet risk triage")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sanctions-update", help="download the latest OFAC SDN list").set_defaults(
        fn=cmd_sanctions_update
    )

    s = sub.add_parser("assess", help="deterministic risk assessment (no LLM, no API key)")
    s.add_argument("address")
    s.add_argument("--depth", type=int, default=2, choices=[1, 2])
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_assess)

    s = sub.add_parser(
        "ingest", help="ingest PDFs/markdown/text files, directories or allowlisted URLs"
    )
    s.add_argument("sources", nargs="+")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("ask", help="ask the document corpus a question")
    s.add_argument("question")
    s.set_defaults(fn=cmd_ask)

    s = sub.add_parser("investigate", help="full multi-agent investigation and report")
    s.add_argument("address")
    s.add_argument("--single", action="store_true", help="use the single-agent baseline instead")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_investigate)

    s = sub.add_parser("serve", help="run the web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
