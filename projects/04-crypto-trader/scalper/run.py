"""
Upbit Scalping Bot Entry Point.

Usage:
  python -m scalper.run                  # Paper trading (default)
  python -m scalper.run --live           # Live trading (requires API keys)
  python -m scalper.run --backtest       # Run backtester
  python -m scalper.run --dashboard      # Dashboard only
  python -m scalper.run --with-dashboard # Trading + dashboard
  python -m scalper.run --no-scanner     # Disable dynamic market scanner
  python -m scalper.run --no-optimizer   # Disable walk-forward optimizer
"""
import argparse
import logging
import sys
import threading

from . import config
from .trader import ScalpTrader
from .backtester import Backtester


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Upbit Scalping Bot")
    parser.add_argument("--live", action="store_true", help="Enable live trading")
    parser.add_argument("--backtest", action="store_true", help="Run backtester")
    parser.add_argument("--dashboard", action="store_true", help="Run dashboard only")
    parser.add_argument("--with-dashboard", action="store_true", help="Trading + dashboard")
    parser.add_argument("--market", default="KRW-BTC", help="Market for backtest")
    parser.add_argument("--days", type=int, default=7, help="Days for backtest")
    parser.add_argument("--no-scanner", action="store_true",
                        help="Disable dynamic market scanner")
    parser.add_argument("--no-optimizer", action="store_true",
                        help="Disable walk-forward optimizer")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("scalper")

    # Apply CLI overrides before creating any components
    if args.no_scanner:
        config.DYNAMIC_MARKETS_ENABLED = False
        logger.info("Dynamic market scanner disabled via --no-scanner")
    if args.no_optimizer:
        config.OPTIMIZER_ENABLED = False
        logger.info("Walk-forward optimizer disabled via --no-optimizer")

    if args.backtest:
        # Backtest mode: always disable scanner/optimizer
        config.DYNAMIC_MARKETS_ENABLED = False
        config.OPTIMIZER_ENABLED = False
        logger.info("=== Backtest Mode ===")
        bt = Backtester(initial_balance=config.PAPER_INITIAL_KRW)
        result = bt.run(market=args.market, days=args.days)
        if result:
            logger.info(f"Backtest complete. Final balance: {result.final_balance:,.0f} KRW")
        return

    paper = not args.live
    trader = ScalpTrader(paper=paper)

    if args.dashboard:
        logger.info("=== Dashboard Only Mode ===")
        from .dashboard import run_dashboard, ws_mgr
        trader.set_ws_callback(ws_mgr.push_event)
        run_dashboard(trader)
        return

    if args.with_dashboard:
        logger.info("=== Trading + Dashboard Mode ===")
        from .dashboard import set_trader, app, ws_mgr, config as cfg
        import uvicorn

        set_trader(trader)
        trader.set_ws_callback(ws_mgr.push_event)

        # Start dashboard in background
        dash_thread = threading.Thread(
            target=uvicorn.run,
            kwargs={"app": app, "host": "0.0.0.0", "port": cfg.DASHBOARD_PORT},
            daemon=True,
        )
        dash_thread.start()
        logger.info(f"Dashboard: http://localhost:{cfg.DASHBOARD_PORT}")

    # Run trader (blocking)
    trader.run()


if __name__ == "__main__":
    main()
