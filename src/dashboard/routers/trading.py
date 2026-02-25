"""Trading endpoints: order placement, active orders, cancellation."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from src.core.models import AssetType, Order, OrderSide, OrderType
from src.dashboard.dependencies import require_user, state
from src.dashboard.schemas import PlaceOrderRequest
from src.db.models import UserRecord

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.post("/order")
async def place_order(req: PlaceOrderRequest, current_user: UserRecord = Depends(require_user)):
    """Place a paper trading order."""
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Please verify your email before trading.")

    if state.executor is None or state.portfolio is None:
        raise HTTPException(status_code=503, detail="Trading not available")

    # Determine asset type from symbol
    asset_type = AssetType.CRYPTO if "/" in req.symbol else AssetType.STOCK

    order = Order(
        symbol=req.symbol,
        side=OrderSide(req.side),
        order_type=OrderType(req.order_type),
        quantity=Decimal(str(req.quantity)),
        asset_type=asset_type,
        limit_price=Decimal(str(req.limit_price)) if req.limit_price else None,
    )

    fill = await state.executor.submit_order(order)
    await state.portfolio.record_fill(fill)

    # Save to DB if available
    if state.db:
        from src.db.models import TradeRecord

        trade_record = TradeRecord(
            symbol=fill.symbol,
            side=fill.side.value,
            quantity=str(fill.quantity),
            price=str(fill.fill_price),
            commission=str(fill.commission),
            strategy="manual",
            paper=True,
            timestamp=fill.timestamp,
        )
        await state.db.save_trade(trade_record)

    return {
        "fill": {
            "id": fill.id,
            "order_id": fill.order_id,
            "symbol": fill.symbol,
            "side": fill.side.value,
            "quantity": str(fill.quantity),
            "fill_price": str(fill.fill_price),
            "timestamp": fill.timestamp.isoformat(),
        }
    }


@router.get("/orders")
async def get_orders(current_user: UserRecord = Depends(require_user)):
    """Get active/pending orders."""
    if state.executor is None:
        return []
    return [
        {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "limit_price": str(order.limit_price) if order.limit_price else None,
        }
        for order in state.executor._open_orders.values()
    ]


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, current_user: UserRecord = Depends(require_user)):
    """Cancel a specific order."""
    if state.executor is None:
        raise HTTPException(status_code=503, detail="Trading not available")
    success = await state.executor.cancel_order(order_id)
    return {"cancelled": success}


@router.post("/cancel-all")
async def cancel_all(current_user: UserRecord = Depends(require_user)):
    """Cancel all open orders."""
    if state.executor is None:
        raise HTTPException(status_code=503, detail="Trading not available")
    count = await state.executor.cancel_all()
    return {"cancelled_count": count}


@router.get("/prices")
async def get_prices(current_user: UserRecord = Depends(require_user)):
    """Current prices for all watched symbols."""
    if state.executor is None:
        return {}
    return {
        symbol: str(price)
        for symbol, price in state.executor._current_prices.items()
    }
