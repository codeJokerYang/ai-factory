"""Validated execution limits and an auditable model-call ledger."""
import time
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class ExecutionLimits(BaseModel):
    max_calls: int = Field(default=20, ge=1, le=100, strict=True)
    max_tokens: int = Field(default=250000, ge=1000, le=2000000, strict=True)
    max_cost: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    currency: Literal['CNY', 'USD'] = 'CNY'


class ModelPrice(BaseModel):
    model: str = Field(min_length=1, max_length=100)
    currency: Literal['CNY', 'USD'] = 'CNY'
    input_per_million: float = Field(ge=0, le=100000, allow_inf_nan=False)
    output_per_million: float = Field(ge=0, le=100000, allow_inf_nan=False)


def cost_summary(calls):
    totals = {}
    for call in calls:
        if call.get('cost') is not None:
            currency = call['price']['currency']
            totals[currency] = round(totals.get(currency, 0) + call['cost'], 8)
    return dict(estimated=totals, unpriced_calls=sum(c.get('cost') is None for c in calls),
                calls=len(calls), reserved_tokens=sum(c['reserved_tokens'] for c in calls),
                actual_tokens=sum((c.get('input_tokens') or 0)+(c.get('output_tokens') or 0)+(c.get('cache_read_input_tokens') or 0)+(c.get('cache_creation_input_tokens') or 0) for c in calls),
                basis='按配置单价估算，缓存输入按统一输入单价计算；不等于供应商账单实收')


class BusinessStep(BaseModel):
    action: Literal['visit', 'click', 'fill', 'text', 'value', 'reload']
    target: str = Field(default='', max_length=500)
    value: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def validate_target(self):
        if self.action != 'reload' and not self.target.strip():
            raise ValueError('测试目标不能为空')
        if self.action == 'visit' and (not self.target.startswith('/') or self.target.startswith('//')):
            raise ValueError('测试访问路径必须是站内绝对路径')
        return self


class BusinessCase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    steps: list[BusinessStep] = Field(min_length=1, max_length=20)


class MeteredLLM:
    def __init__(self, client, state, checkpoint, prices=None):
        self.client, self.state, self.checkpoint = client, state, checkpoint
        self.prices = prices or {}
        if hasattr(client, '_client') and hasattr(client._client, 'with_options'):
            client._client = client._client.with_options(max_retries=0)

    def complete(self, **kwargs):
        state = self.state
        from . import config
        kwargs.setdefault('max_tokens', config.MAX_TOKENS)
        # UTF-8 byte count is deliberately conservative; it is a reservation,
        # not a claimed provider token count or a monetary price.
        reserved = len((kwargs.get('system', '') + kwargs.get('prompt', '')).encode('utf-8')) + kwargs['max_tokens'] + 1024
        used = sum(call['reserved_tokens'] for call in state.model_calls)
        if len(state.model_calls) >= state.limits.max_calls or used + reserved > state.limits.max_tokens:
            raise ValueError('模型预算上限已到：停止新增调用，请查看用量并调整预算后恢复')
        configured_price = self.prices.get(kwargs.get('model'))
        price = dict(configured_price) if configured_price else None
        estimated_max = (reserved * max(price['input_per_million'], price['output_per_million']) / 1000000) if price else None
        if state.limits.max_cost is not None:
            if not price or price['currency'] != state.limits.currency:
                raise ValueError('金额预算需要为当前模型配置同币种单价')
            if any(not c.get('price') or c['price']['currency'] != state.limits.currency for c in state.model_calls):
                raise ValueError('恢复链包含未计价或其他币种调用，无法验证累计金额预算')
            spent = sum(c['cost'] if c.get('cost') is not None else c.get('reserved_cost', 0) for c in state.model_calls)
            if spent + estimated_max > state.limits.max_cost:
                raise ValueError('金额预算不足以覆盖下一次调用预留，已停止新增调用')
        call = dict(run_id=state.project_id, model=kwargs.get('model', ''), reserved_tokens=reserved, input_tokens=None,
                    output_tokens=None, status='started', duration_seconds=None, cost=None)
        call.update(price=price, reserved_cost=estimated_max)
        state.model_calls.append(call)
        self.checkpoint(state)  # Reserve before contacting provider; crashes keep the reservation.
        start = time.monotonic()
        try:
            result = self.client.complete(**kwargs)
            usage = getattr(self.client, 'last_usage', None)
            if isinstance(usage, dict):
                call.update(usage)
                if price and all(isinstance(call.get(k), int) and call[k]>=0 for k in ('input_tokens','output_tokens')):
                    inputs=call['input_tokens']+(call.get('cache_read_input_tokens') or 0)+(call.get('cache_creation_input_tokens') or 0)
                    call['cost']=round((inputs*price['input_per_million']+call['output_tokens']*price['output_per_million'])/1000000,8)
            call['status'] = 'completed'
            return result
        except Exception:
            call['status'] = 'failed'
            raise
        finally:
            call['duration_seconds'] = round(time.monotonic() - start, 3)
            self.checkpoint(state)
