"""AutoIncome Runner - Entry point for the product generation pipeline.

Usage:
    python run.py                    # Run daily generation
    python run.py --custom           # Custom generation with interactive options
    python run.py --schedule         # Show Windows Task Scheduler setup instructions
"""
import sys
import argparse
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from autoincome.main import run_daily_generation, run_custom_generation
from autoincome.config import PALETTES, NICHES, OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser(description="AutoIncome - Digital Product Generator")
    parser.add_argument("--custom", action="store_true", help="Custom generation mode")
    parser.add_argument("--palette", type=str, default=None,
                        help=f"Color palette: {', '.join(PALETTES.keys())}")
    parser.add_argument("--niche", type=str, default=None,
                        help=f"Niche: {', '.join(NICHES.keys())}")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--wallpapers", type=int, default=5, help="Number of wallpapers")
    parser.add_argument("--quotes", type=int, default=3, help="Number of quotes")
    parser.add_argument("--patterns", type=int, default=3, help="Number of patterns")
    parser.add_argument("--pod", type=int, default=2, help="Number of POD designs")
    parser.add_argument("--schedule", action="store_true",
                        help="Show scheduling instructions")

    args = parser.parse_args()

    if args.schedule:
        show_schedule_instructions()
        return

    if args.custom:
        palette = args.palette or "midnight_gold"
        niche = args.niche or "motivational"
        output = args.output or str(OUTPUT_DIR / "custom")

        print(f"Custom Generation: palette={palette}, niche={niche}")
        products, listings = run_custom_generation(
            palette, niche, output,
            n_wallpapers=args.wallpapers,
            n_quotes=args.quotes,
            n_patterns=args.patterns,
            n_pod=args.pod,
            seed=args.seed,
        )
        print(f"Generated {len(products)} products with {len(listings)} listings")
    else:
        report = run_daily_generation(seed=args.seed)
        print(f"\nDaily generation complete. See: {report['output_directory']}")


def show_schedule_instructions():
    project_dir = Path(__file__).parent
    python_path = sys.executable
    script_path = project_dir / "run.py"

    print(f"""
{'='*60}
  AutoIncome - Windows Task Scheduler Setup
{'='*60}

To run this automatically every day while you're at work:

1. Open Windows Task Scheduler:
   - Press Win+R, type "taskschd.msc", press Enter

2. Click "Create Basic Task..."
   - Name: AutoIncome Daily Generation
   - Trigger: Daily
   - Time: 09:00 AM (or whenever you want)

3. Action: Start a Program
   - Program: {python_path}
   - Arguments: "{script_path}"
   - Start in: {project_dir}

4. Click Finish

Alternative - PowerShell one-liner to create the task:

$action = New-ScheduledTaskAction -Execute "{python_path}" -Argument '"{script_path}"' -WorkingDirectory "{project_dir}"
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-ScheduledTask -TaskName "AutoIncome" -Action $action -Trigger $trigger -Description "Daily digital product generation"

{'='*60}
  After setup, the system will generate products daily.
  Just upload them to Etsy/Gumroad/Redbubble when you get home!
{'='*60}
""")


if __name__ == "__main__":
    main()
