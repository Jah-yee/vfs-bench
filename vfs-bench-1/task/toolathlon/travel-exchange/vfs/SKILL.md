---
name: workspace-commands
description: The shell commands, task tools, and python3 interpreter available in this workspace.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip  curl

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## yahoo-finance

Use `yahoo-finance <command> '<JSON arguments>'`. Run
`yahoo-finance <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `yahoo-finance get-historical-stock-prices` | `{ticker: str, period?: str = "1mo", interval?: str = "1d", start_date?: str = null, end_date?: str = null, auto_adjust?: bool = true}` | Get historical stock prices for a given ticker symbol from yahoo finance. Include the following information: Date, Open, High, Low, Close, Volume, Dividends, Stock Splits, and optionally Adj Close. Args: ticker: str The ticker symbol of the stock to get historical prices for, e.g. "AAPL" period : str Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max Used only when both start_date and end_date are not provided Default is "1mo" interval : str Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo Intraday data cannot extend last 60 days Default is "1d" start_date: str (optional) The start date for historical data (format: 'YYYY-MM-DD'), e.g. "2024-01-01" If provided, period parameter will be ignored end_date: str (optional) The end date for historical data (format: 'YYYY-MM-DD'), e.g. "2024-12-31" If not provided, defaults to current date auto_adjust: bool (optional) If True (default), returns prices adjusted for dividends and stock splits (Open, High, Low, Close are adjusted) If False, returns raw unadjusted prices and includes 'Adj Close' column Default is True |
| `yahoo-finance get-stock-price-by-date` | `{ticker: str, date: str, find_nearest?: bool = true, auto_adjust?: bool = true}` | Get stock price for a specific date. This tool is more efficient than getting historical prices when you only need data for one specific date. Args: ticker: str The ticker symbol of the stock to get price for, e.g. "AAPL" date: str The specific date to get price for (format: 'YYYY-MM-DD'), e.g. "2024-01-15" find_nearest: bool If True and the exact date has no trading data (weekend/holiday), return the nearest trading day data. If False, return error for non-trading days. Default is True. auto_adjust: bool (optional) If True (default), returns prices adjusted for dividends and stock splits If False, returns raw unadjusted prices Default is True |
| `yahoo-finance get-stock-info` | `{ticker: str}` | Get stock information for a given ticker symbol from yahoo finance. Include the following information: Stock Price & Trading Info, Company Information, Financial Metrics, Earnings & Revenue, Margins & Returns, Dividends, Balance Sheet, Ownership, Analyst Coverage, Risk Metrics, Other. Args: ticker: str The ticker symbol of the stock to get information for, e.g. "AAPL" |
| `yahoo-finance get-yahoo-finance-news` | `{ticker: str}` | Get news for a given ticker symbol from yahoo finance. Args: ticker: str The ticker symbol of the stock to get news for, e.g. "AAPL" |
| `yahoo-finance get-stock-actions` | `{ticker: str}` | Get stock dividends and stock splits for a given ticker symbol from yahoo finance. Args: ticker: str The ticker symbol of the stock to get stock actions for, e.g. "AAPL" |
| `yahoo-finance get-financial-statement` | `{ticker: str, financial_type: str}` | Get financial statement for a given ticker symbol from yahoo finance. You can choose from the following financial statement types: income_stmt, quarterly_income_stmt, balance_sheet, quarterly_balance_sheet, cashflow, quarterly_cashflow. Args: ticker: str The ticker symbol of the stock to get financial statement for, e.g. "AAPL" financial_type: str The type of financial statement to get. You can choose from the following financial statement types: income_stmt, quarterly_income_stmt, balance_sheet, quarterly_balance_sheet, cashflow, quarterly_cashflow. |
| `yahoo-finance get-holder-info` | `{ticker: str, holder_type: str}` | Get holder information for a given ticker symbol from yahoo finance. You can choose from the following holder types: major_holders, institutional_holders, mutualfund_holders, insider_transactions, insider_purchases, insider_roster_holders. Args: ticker: str The ticker symbol of the stock to get holder information for, e.g. "AAPL" holder_type: str The type of holder information to get. You can choose from the following holder types: major_holders, institutional_holders, mutualfund_holders, insider_transactions, insider_purchases, insider_roster_holders. |
| `yahoo-finance get-option-expiration-dates` | `{ticker: str}` | Fetch the available options expiration dates for a given ticker symbol. Args: ticker: str The ticker symbol of the stock to get option expiration dates for, e.g. "AAPL" |
| `yahoo-finance get-option-chain` | `{ticker: str, expiration_date: str, option_type: str}` | Fetch the option chain for a given ticker symbol, expiration date, and option type. Args: ticker: str The ticker symbol of the stock to get option chain for, e.g. "AAPL" expiration_date: str The expiration date for the options chain (format: 'YYYY-MM-DD') option_type: str The type of option to fetch ('calls' or 'puts') |
| `yahoo-finance get-recommendations` | `{ticker: str, recommendation_type: str, months_back?: int = 12}` | Get recommendations or upgrades/downgrades for a given ticker symbol from yahoo finance. You can also specify the number of months back to get upgrades/downgrades for, default is 12. Args: ticker: str The ticker symbol of the stock to get recommendations for, e.g. "AAPL" recommendation_type: str The type of recommendation to get. You can choose from the following recommendation types: recommendations, upgrades_downgrades. months_back: int The number of months back to get upgrades/downgrades for, default is 12. |

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
