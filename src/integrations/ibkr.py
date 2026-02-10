from __future__ import annotations

from decimal import Decimal


class IBKRFeed:
    """Wrapper around ib_insync for stock market data."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self._host = host
        self._port = port
        self._client_id = client_id
        self._ib = None

    async def connect(self) -> None:
        from ib_insync import IB

        self._ib = IB()
        await self._ib.connectAsync(self._host, self._port, clientId=self._client_id)

    async def disconnect(self) -> None:
        if self._ib:
            self._ib.disconnect()

    async def get_price(self, symbol: str) -> Decimal:
        from ib_insync import Stock

        contract = Stock(symbol, "SMART", "USD")
        self._ib.qualifyContracts(contract)
        ticker = self._ib.reqMktData(contract)
        await self._ib.sleep(1)
        price = ticker.marketPrice()
        self._ib.cancelMktData(contract)
        return Decimal(str(price))

    async def get_order_book(self, symbol: str) -> dict:
        from ib_insync import Stock

        contract = Stock(symbol, "SMART", "USD")
        self._ib.qualifyContracts(contract)
        book = self._ib.reqMktDepth(contract, numRows=5)
        await self._ib.sleep(1)
        self._ib.cancelMktDepth(contract)
        return {
            "bids": [(str(d.price), str(d.size)) for d in book if d.side == 1],
            "asks": [(str(d.price), str(d.size)) for d in book if d.side == 0],
        }
