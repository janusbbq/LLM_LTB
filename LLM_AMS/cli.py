"""LLM-AMS terminal interface.

UX conventions (defined in ``agent.utils.theme`` + ``agent.utils.display``):
    [?]   blue  — choice required from user
    [i]   grey  — passive info / hint
    [✓]   green — success / state change
    [✗]   red   — failure
    ❯     green — input prompt

Startup flow:
    banner (logo + LLM·LTB·AMS)
    [?] provider  →  [?] routine (routines table)  →  [?] solver (solver table)
    bootstrap case (ex2 default)  →  one-line "Loaded ..." confirmation

Per-turn flow:
    sticky status bar  →  ❯ input  →  node trace  →  agent response
"""

from datetime import datetime

from rich.table import Table

from agent.ams_engine.formulations import get_formulation
from agent.ams_engine.routines import (
    compatible_solvers,
    installed_solvers,
    routine_family,
)
from agent.ams_engine.snapshots import get_snapshot
from agent.core import setup_dependencies
from agent.memory_service import JsonFileAMSRunMemory
from agent.schemas.study import LoadSweep, StudySpec
from agent.session import SessionManager
from agent.tools.run_small_study import run_small_study
from agent.tools.write_report import write_report
from agent.utils.display import (
    choice_prompt,
    console,
    display_banner,
    display_formulation,
    display_help,
    display_initial_case_summary,
    display_response,
    display_routines_table,
    display_snapshot,
    display_solver_table,
    display_status_bar,
    fail,
    info,
    input_prompt,
    ok,
)
from agent.workflows.workflow import create_workflow


DEFAULT_CASE    = "5bus/pjm5bus_demo.xlsx"
DEFAULT_ROUTINE = "RTED"


# ------------------------------------------------------------------ Choice prompts
def _ask_provider() -> str:
    info("Choose how to talk to the LLM. Ollama runs locally; OpenAI needs an API key.")
    raw = choice_prompt("Which model provider?  (ollama / openai)", default="ollama")
    raw = raw.strip().lower()
    if raw not in ("ollama", "openai"):
        if raw:
            console.print(f"[warn]Unrecognized '{raw}' — using ollama.[/]")
        raw = "ollama"
    console.print()
    return raw


def _ask_routine() -> str:
    display_routines_table()
    info("RTED (Real-Time Economic Dispatch) is the most common starting point. "
         "It extends DCOPF with reserve regulation.")
    raw = choice_prompt("Which routine?", default=DEFAULT_ROUTINE)
    raw = raw.strip().upper()
    if not raw:
        raw = DEFAULT_ROUTINE
    if routine_family(raw) == "unknown":
        console.print(f"[warn]Unknown routine '{raw}' — falling back to {DEFAULT_ROUTINE}.[/]")
        raw = DEFAULT_ROUTINE
    console.print()
    return raw


def _ask_solver(routine: str) -> str:
    compat = compatible_solvers(routine)
    if not compat:
        installed = installed_solvers()
        fail(f"No installed solver is compatible with {routine}. Installed: {installed}.")
        return installed[0] if installed else "CLARABEL"
    default = compat[0]
    info(f"These solvers can handle a {routine} problem.")
    display_solver_table(compat, default)
    raw = choice_prompt("Which solver?", default=default)
    raw = raw.strip().upper()
    if not raw:
        raw = default
    if raw not in compat and "(internal: pypower)" not in compat:
        console.print(f"[warn]Solver '{raw}' not compatible with {routine} — using {default}.[/]")
        raw = default
    console.print()
    return raw


# ------------------------------------------------------------------ Study command
_DEFAULT_SCALES = [0.90, 0.95, 1.00, 1.05, 1.10]


def _parse_scales(token: str) -> list[float]:
    return [float(x) for x in token.split(",") if x.strip()]


def _looks_like_scales(token: str) -> bool:
    try:
        _parse_scales(token)
        return "," in token or token.replace(".", "", 1).isdigit()
    except ValueError:
        return False


def _run_study(user_input: str, session) -> None:
    """Run a small load-scenario sweep from the current case/routine/solver.

    Usage:
        study                       ±5% / ±10% on all loads
        study PQ_1                  sweep load PQ_1
        study PQ_1 0.9,1.0,1.1      custom scales on PQ_1
        study 0.9,0.95,1.05,1.1     custom scales on all loads

    Runs on a fresh context from the clean base case, so it does not disturb
    the live interactive session (its mods, routine, etc. are untouched).
    """
    inputs = session.state["inputs"]
    args = user_input.split()[1:]

    target = "all"
    scales = list(_DEFAULT_SCALES)
    if args:
        if _looks_like_scales(args[0]):
            scales = _parse_scales(args[0])
        else:
            target = args[0]
            if len(args) >= 2:
                try:
                    scales = _parse_scales(args[1])
                except ValueError:
                    fail("Bad scale list. Example: [value]study PQ_1 0.9,1.0,1.1[/]")
                    return

    spec = StudySpec(
        base_case=inputs.case_path,
        routine=inputs.routine,
        solver=inputs.solver,
        load_sweep=LoadSweep(target=target, scales=scales),
    )
    out_dir = f"generated/study_{datetime.now():%Y%m%d_%H%M%S}"
    info(f"Running study — routine [value]{spec.routine}[/], solver [value]{spec.solver}[/], "
         f"target [value]{target}[/], [value]{len(scales)}[/] scenarios (from clean base case)…")

    memory = JsonFileAMSRunMemory(root_dir=f"{out_dir}/run_memory")
    result = run_small_study(spec, memory=memory, output_dir=out_dir)

    table = Table(show_edge=True)
    table.add_column("scenario")
    table.add_column("label")
    table.add_column("scale", justify="right")
    table.add_column("objective", justify="right")
    table.add_column("status")
    for s in result["summary"]:
        obj = f"{s['objective']:.6f}" if isinstance(s["objective"], (int, float)) else "—"
        table.add_row(s["scenario_id"], s["label"], f"{s['load_scale']:.2f}", obj, s["status"])
    console.print(table)

    n_ok = sum(1 for s in result["summary"] if s["status"] == "optimal")
    ok(f"Study complete — [value]{n_ok}/{len(result['summary'])}[/] solved.")
    info(f"results table: [value]{result['results_table']}[/]")
    info(f"run records:   [value]{out_dir}/run_memory[/]  (pg, plf, pd, pi/LMP, load_changes, …)")

    # Auto-build the cross-scenario report (Option A) over the fresh study.
    # A report failure must not lose the study results, so isolate it.
    try:
        report = write_report(out_dir)
        info(f"report:        [value]{report['report']}[/]  "
             "(objective Δ, LMP ranking, dispatch shifts)")
    except Exception as exc:
        fail(f"Report generation failed: {exc}")


# ------------------------------------------------------------------ Main loop
def run_cli():
    display_banner()

    provider = _ask_provider()
    routine  = _ask_routine()
    solver   = _ask_solver(routine)

    info(f"Booting agent — provider [value]{provider}[/], routine [value]{routine}[/], "
         f"solver [value]{solver}[/]…")
    console.print()

    llm, prompts, ams_ctx = setup_dependencies(provider)
    graph = create_workflow(llm, prompts, ams_ctx)

    session = SessionManager(graph, llm, ams_ctx, provider=provider,
                             case_path=DEFAULT_CASE, routine=routine, solver=solver)
    info("Loading default case (ex2 setup)…")
    session.bootstrap()
    display_initial_case_summary(ams_ctx.case_info())

    # Routine-aware data + math formulation — shown after each case/routine change
    display_snapshot(get_snapshot(ams_ctx, routine))
    display_formulation(get_formulation(routine))

    # First-turn help (auto-shown once; reachable later via '?')
    display_help()

    is_first_turn = True
    last_case = session.state["inputs"].case_path
    last_routine = session.state["inputs"].routine

    while True:
        display_status_bar(session.state["inputs"])
        user_input = input_prompt(hint=is_first_turn)
        is_first_turn = False
        if not user_input:
            continue
        low = user_input.lower()
        if low in ("quit", "q", "exit"):
            ok("Goodbye!")
            return
        if low in ("?", "h", "help"):
            display_help()
            continue
        if low == "study" or low.startswith("study "):
            try:
                _run_study(user_input, session)
            except Exception as exc:
                fail(f"Study error: {exc}")
            continue

        # Execute turn — each node self-announces via display_executing_node;
        # we render the final assistant message at the end as Markdown.
        final_content = None
        try:
            for node_name, state_update in session.execute_turn_streaming(user_input):
                if "messages" in state_update and state_update["messages"]:
                    last = state_update["messages"][-1]
                    if hasattr(last, "content") and last.content:
                        final_content = last.content
        except Exception as exc:
            fail(f"Error: {exc}")
            continue

        if final_content:
            display_response(final_content)

        # If the case or active routine just changed, re-display the
        # routine-aware snapshot + math formulation so the user always
        # sees the right reference for what they're about to solve.
        cur_case = session.state["inputs"].case_path
        cur_routine = session.state["inputs"].routine
        if cur_case != last_case or cur_routine != last_routine:
            display_snapshot(get_snapshot(ams_ctx, cur_routine))
            display_formulation(get_formulation(cur_routine))
            last_case, last_routine = cur_case, cur_routine


if __name__ == "__main__":
    run_cli()
