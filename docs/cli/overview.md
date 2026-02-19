# CLI Overview

The trade-bot CLI is built on [Typer](https://typer.tiangolo.com/) and provides
subcommands for configuration, provider management, sentiment analysis, ML
pipelines, risk management, and analytics. Output is formatted with
[Rich](https://rich.readthedocs.io/) for tables and colored text.

## Entry point

The CLI is registered as a console script in `pyproject.toml`:

```toml
[project.scripts]
tradebot = "src.cli.main:app"
```

Run it with:

```bash
uv run tradebot --help
```

## Architecture

`src/cli/main.py` creates a root `typer.Typer` app and mounts each command
group as a sub-Typer:

```python
app = typer.Typer(name="tradebot", help="Trading bot CLI.", no_args_is_help=True)
app.add_typer(analytics_app, name="analytics")
app.add_typer(config_app,    name="config")
app.add_typer(ml_app,        name="ml")
app.add_typer(providers_app, name="providers")
app.add_typer(risk_app,       name="risk")
app.add_typer(sentiment_app,  name="sentiment")
app.add_typer(simulation_app, name="simulation")
```

Each command file (`src/cli/<name>_cmd.py`) exports its own `app` Typer
instance which is imported and mounted in `main.py`.

## Available command groups

| Group        | File                        | Description                              |
| ------------ | --------------------------- | ---------------------------------------- |
| `config`     | `src/cli/config_cmd.py`     | Validate, show, and inspect config files |
| `providers`  | `src/cli/providers_cmd.py`  | List providers, run health checks        |
| `sentiment`  | `src/cli/sentiment_cmd.py`  | Sentiment pipeline status and scores     |
| `ml`         | `src/cli/ml_cmd.py`         | ML pipeline status and feature store     |
| `risk`       | `src/cli/risk_cmd.py`       | Risk settings and regime limits          |
| `analytics`  | `src/cli/analytics_cmd.py`  | Analytics module status and attribution  |
| `simulation` | `src/cli/simulation_cmd.py` | Walk-forward backtests and MC projections |

## Command details

### config

| Command    | Description                                  |
| ---------- | -------------------------------------------- |
| `validate` | Validate a settings YAML file                |
| `show`     | Load and display config (YAML or JSON)       |
| `schema`   | Print JSON schema for a configuration model  |

```bash
uv run tradebot config validate --config config/settings.yaml
uv run tradebot config show --config config/settings.yaml --format json
uv run tradebot config schema RiskSettings
```

### providers

| Command | Description                              |
| ------- | ---------------------------------------- |
| `list`  | List known provider implementations      |
| `health`| Check health of registered providers     |

```bash
uv run tradebot providers list
uv run tradebot providers list --protocol sentiment
uv run tradebot providers health --mock
```

### sentiment

| Command  | Description                            |
| -------- | -------------------------------------- |
| `status` | Show sentiment pipeline status summary |
| `scores` | Show sentiment scores for a symbol     |

```bash
uv run tradebot sentiment status
uv run tradebot sentiment scores --symbol BTC
```

### ml

| Command    | Description                          |
| ---------- | ------------------------------------ |
| `status`   | Show ML pipeline status summary      |
| `features` | Show stored features for a symbol    |

```bash
uv run tradebot ml status
uv run tradebot ml features --symbol BTC
```

### risk

| Command  | Description                            |
| -------- | -------------------------------------- |
| `status` | Show current risk settings summary     |
| `limits` | Show regime-specific risk limits       |

```bash
uv run tradebot risk status
uv run tradebot risk limits --regime high
```

### analytics

| Command       | Description                          |
| ------------- | ------------------------------------ |
| `status`      | Show analytics module summary        |
| `attribution` | Show example attribution format      |

```bash
uv run tradebot analytics status
uv run tradebot analytics attribution
```

### simulation

| Command | Description                                                     |
| ------- | --------------------------------------------------------------- |
| `run`   | Run walk-forward backtests and Monte Carlo projections          |

```bash
# Full simulation with all 16 stocks and all risk levels
uv run tradebot simulation run

# Specific stocks with custom balance
uv run tradebot simulation run --stocks AAPL --stocks MSFT --stocks GOOGL --balance 30000

# Portfolio mode with custom weights and weekly rebalancing
uv run tradebot simulation run --portfolio --stocks AAPL --stocks MSFT --weights '{"AAPL":0.6,"MSFT":0.4}' --rebalance weekly

# Quick simulation with fewer MC paths
uv run tradebot simulation run --stocks AAPL --test-days 10 --train-days 20 --mc-sims 50

# Specific risk levels
uv run tradebot simulation run --risk moderate --risk aggressive

# JSON output
uv run tradebot simulation run --stocks AAPL --json
```

**Flags:**

| Flag            | Default | Description                                    |
| --------------- | ------- | ---------------------------------------------- |
| `--stocks`      | all 16  | Stock symbols to simulate                      |
| `--balance`     | 10000   | Starting balance in USD                        |
| `--train-days`  | 60      | Training window in trading days                |
| `--test-days`   | 30      | Test/simulation window in trading days         |
| `--risk`        | all     | Risk levels (conservative, moderate, etc.)     |
| `--mc-sims`     | 1000    | Number of Monte Carlo simulation paths         |
| `--json`        | false   | Output raw JSON instead of Rich tables         |
| `--portfolio`   | false   | Enable portfolio simulation mode               |
| `--weights`     | none    | Custom allocation weights as JSON string       |
| `--rebalance`   | none    | Rebalance frequency: none/daily/weekly/monthly |

**Output includes:**
- Risk level comparison table (return %, Sharpe, max drawdown, trades)
- Per-stock results table per risk level
- Portfolio equity curve chart (portfolio mode)
- Portfolio metrics panel (Sharpe, Sortino, Calmar)
- Monte Carlo projection tables (P5/Median/P95)
- Win rate heatmap (stocks x risk levels)
- Return comparison bar chart
- Optimal risk level recommendation

## How to add a new CLI command

1. **Create the command file.** Add `src/cli/<name>_cmd.py` with a new Typer
   app:

   ```python
   """My new command group."""
   from __future__ import annotations

   import typer
   from rich.console import Console

   app = typer.Typer(
       name="mygroup", help="My command group.", no_args_is_help=True
   )
   console = Console()


   @app.command()
   def hello(name: str = typer.Option("world", help="Who to greet")) -> None:
       """Say hello."""
       console.print(f"Hello, {name}!")
   ```

2. **Mount it in `main.py`.** Import the app and add it:

   ```python
   from src.cli.mygroup_cmd import app as mygroup_app
   app.add_typer(mygroup_app, name="mygroup")
   ```

3. **Add tests.** Create `tests/unit/cli/test_mygroup_cmd.py`:

   ```python
   from typer.testing import CliRunner
   from src.cli.main import app

   runner = CliRunner()

   class TestMyGroupHello:
       def test_default_greeting(self):
           result = runner.invoke(app, ["mygroup", "hello"])
           assert result.exit_code == 0
           assert "Hello, world!" in result.output
   ```

4. **Run the tests:**

   ```bash
   uv run pytest tests/unit/cli/test_mygroup_cmd.py -v
   ```

## Conventions

- Each command file creates a module-level `Console` for Rich output.
- Commands that call async code use `asyncio.run()` (see `providers_cmd.py`
  for an example).
- Use `typer.Option` and `typer.Argument` with `Annotated` type hints for
  CLI parameters.
- Exit with `raise typer.Exit(code=1)` for error conditions.
- Typer apps use `no_args_is_help=True` so running a group with no
  subcommand prints help automatically.
