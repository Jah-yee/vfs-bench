"""Lossless JSON transport for the original Yahoo SDK's read results."""
from collections import namedtuple
from datetime import date, datetime

import pandas as pd
import requests
import yfinance as yf

REAL_TICKER = yf.Ticker


def encode(value):
    if value is pd.NaT:
        return {'$type': 'NaT'}
    if value is pd.NA:
        return {'$type': 'NA'}
    if isinstance(value, pd.DataFrame):
        return {
            '$type':
            'frame',
            'columns':
            encode(value.columns),
            'index':
            encode(value.index),
            'dtypes': [str(dtype) for dtype in value.dtypes],
            'data': [[encode(item) for item in row]
                     for row in value.itertuples(index=False, name=None)]
        }
    if isinstance(value, pd.Series):
        return {
            '$type': 'series',
            'index': encode(value.index),
            'name': encode(value.name),
            'dtype': str(value.dtype),
            'data': [encode(item) for item in value]
        }
    if isinstance(value, pd.Index):
        return {
            '$type': 'index',
            'class': type(value).__name__,
            'dtype': str(value.dtype),
            'names': list(value.names),
            'data': [encode(item) for item in value]
        }
    if isinstance(value, (datetime, date)):
        return {'$type': type(value).__name__, 'value': value.isoformat()}
    if isinstance(value, tuple):
        return {
            '$type': 'tuple',
            'fields': getattr(value, '_fields', None),
            'data': [encode(item) for item in value]
        }
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if hasattr(value, 'item'):
        return encode(value.item())
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    kind = value.get('$type')
    if kind == 'index':
        values = [decode(item) for item in value['data']]
        if value['class'] == 'MultiIndex':
            return pd.MultiIndex.from_tuples(values, names=value['names'])
        if value['class'] == 'RangeIndex' and values:
            step = values[1] - values[0] if len(values) > 1 else 1
            return pd.RangeIndex(values[0],
                                 values[-1] + step,
                                 step,
                                 name=value['names'][0])
        return pd.Index(values, dtype=value['dtype'], name=value['names'][0])
    if kind == 'frame':
        frame = pd.DataFrame(decode(value['data']),
                             index=decode(value['index']),
                             columns=decode(value['columns']))
        for i, dtype in enumerate(value['dtypes']):
            frame.isetitem(i, frame.iloc[:, i].astype(dtype))
        return frame
    if kind == 'series':
        return pd.Series(decode(value['data']),
                         index=decode(value['index']),
                         name=decode(value['name']),
                         dtype=value['dtype'])
    if kind in ('Timestamp', 'datetime', 'date'):
        return {
            'Timestamp': pd.Timestamp,
            'datetime': datetime.fromisoformat,
            'date': date.fromisoformat
        }[kind](value['value'])
    if kind == 'NaT':
        return pd.NaT
    if kind == 'NA':
        return pd.NA
    if kind == 'tuple':
        values = decode(value['data'])
        return namedtuple('Options', value['fields'])(
            *values) if value['fields'] else tuple(values)
    return {key: decode(item) for key, item in value.items()}


PROPERTIES = frozenset(
    ('isin info news actions income_stmt quarterly_income_stmt balance_sheet '
     'quarterly_balance_sheet cashflow quarterly_cashflow major_holders '
     'institutional_holders mutualfund_holders insider_transactions '
     'insider_purchases '
     'insider_roster_holders options recommendations upgrades_downgrades'
     ).split())
METHODS = frozenset(('history', 'option_chain', 'get_news'))


def install(endpoint):

    class Ticker:

        def __init__(self, ticker, *args, **kwargs):
            if args or kwargs:
                raise ValueError(
                    'Unsupported original Yahoo constructor arguments')
            self.ticker = ticker

        def request(self, name, args=(), kwargs=None):
            response = requests.post(endpoint + '/sdk',
                                     json={
                                         'ticker': self.ticker,
                                         'name': name,
                                         'args': encode(args),
                                         'kwargs': encode(kwargs or {})
                                     },
                                     timeout=120)
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                raise RuntimeError(result['error'])
            return decode(result['value'])

        def __getattr__(self, name):
            if name in METHODS:
                return lambda *args, **kwargs: self.request(name, args, kwargs)
            if name in PROPERTIES:
                return self.request(name)
            raise AttributeError(name)

    yf.Ticker = Ticker
