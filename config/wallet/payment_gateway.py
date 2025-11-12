"""
سرویس یکپارچه‌سازی با درگاه‌های پرداخت
"""
import uuid
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings


@dataclass
class PaymentResult:
    success: bool
    authority: Optional[str] = None
    payment_url: Optional[str] = None
    ref_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[Any] = None
    raw_response: Optional[Dict[str, Any]] = None
    gateway: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class SepehrPaymentGateway:
    """درگاه پرداخت الکترونیک سپهر (صادرات) با فرایند توکنی"""

    STATUS_SUCCESS_VALUES = {'0', 0, 'ok', 'OK', 'Ok', 'Success', 'success'}

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.enabled = self.config.get('ENABLED', True)

    def ensure_enabled(self):
        if not self.enabled:
            raise ValueError("Sepehr gateway is disabled")

    def _get_terminal_id(self) -> str:
        terminal_id = str(self.config.get('TERMINAL_ID') or '').strip()
        if not terminal_id:
            raise ValueError("Sepehr terminal id is not configured")
        return terminal_id

    def _get_timeout(self) -> int:
        return int(self.config.get('TIMEOUT', 10))

    def create_payment_request(
        self,
        amount: Decimal,
        description: str,
        callback_url: str,
        user_phone: Optional[str] = None,
        user_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentResult:
        self.ensure_enabled()
        metadata = metadata or {}
        invoice_id = metadata.get('invoice_id')
        payload = metadata.get('payload', self.config.get('DEFAULT_PAYLOAD', '')) or ''
        terminal_id = self._get_terminal_id()

        if not invoice_id:
            raise ValueError("Sepehr gateway requires invoice_id in metadata")

        token_url = self.config.get('TOKEN_URL') or 'https://sepehr.shaparak.ir/Rest/V1/PeymentApi/GetToken'
        payment_url = (self.config.get('PAYMENT_URL') or 'https://sepehr.shaparak.ir/Payment/Pay').rstrip('/')

        request_body = {
            "TerminalID": terminal_id,
            "Amount": str(int(Decimal(amount))),
            "InvoiceID": str(invoice_id),
            "callbackURL": callback_url,
            "payload": payload,
        }

        timeout = self._get_timeout()

        try:
            response = requests.post(token_url, json=request_body, timeout=timeout)
            response.raise_for_status()
            result = response.json()

            status_value = result.get('Status')
            access_token = result.get('Accesstoken') or result.get('AccessToken')

            if (status_value in self.STATUS_SUCCESS_VALUES or str(status_value) in self.STATUS_SUCCESS_VALUES) and access_token:
                redirect_url = f"{payment_url}?token={access_token}&terminalId={terminal_id}"
                return PaymentResult(
                    success=True,
                    authority=access_token,
                    payment_url=redirect_url,
                    gateway=self.name,
                    raw_response=result,
                    extra={
                        'terminal_id': terminal_id,
                        'invoice_id': invoice_id,
                        'payload': payload,
                        'token_url': token_url,
                    }
                )

            error_message = result.get('Message') or result.get('error') or 'Sepehr token request failed'
            return PaymentResult(
                success=False,
                error=error_message,
                error_code=status_value,
                raw_response=result,
                gateway=self.name
            )
        except requests.exceptions.RequestException as exc:
            return PaymentResult(
                success=False,
                error=f'Connection error: {exc}',
                gateway=self.name
            )
        except Exception as exc:
            return PaymentResult(
                success=False,
                error=f'Unexpected error: {exc}',
                gateway=self.name
            )

    def verify_payment(
        self,
        authority: str,
        amount: Decimal,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentResult:
        self.ensure_enabled()
        metadata = metadata or {}

        digital_receipt = metadata.get('digital_receipt')
        terminal_id = metadata.get('terminal_id') or self.config.get('TERMINAL_ID')

        if not digital_receipt:
            raise ValueError("Sepehr verification requires digital_receipt in metadata")
        if not terminal_id:
            raise ValueError("Sepehr verification requires terminal_id in metadata or config")

        advice_url = self.config.get('ADVICE_URL') or 'https://sepehr.shaparak.ir/Rest/V1/PeymentApi/Advice'
        timeout = self._get_timeout()

        request_body = {
            "digitalreceipt": digital_receipt,
            "Tid": str(terminal_id),
        }

        try:
            response = requests.post(advice_url, json=request_body, timeout=timeout)
            response.raise_for_status()
            result = response.json()

            status_value = result.get('Status')

            if status_value in {'Ok', 'OK', 'ok', 'Duplicate', 'duplicate', '0', 0}:
                ref_id = result.get('ReturnId') or digital_receipt
                return PaymentResult(
                    success=True,
                    authority=authority,
                    ref_id=str(ref_id),
                    gateway=self.name,
                    raw_response=result,
                    extra={
                        'digital_receipt': digital_receipt,
                        'terminal_id': terminal_id,
                        'status': status_value,
                    }
                )

            error_message = result.get('Message') or 'Sepehr advice verification failed'
            return PaymentResult(
                success=False,
                error=error_message,
                error_code=status_value,
                raw_response=result,
                gateway=self.name
            )
        except requests.exceptions.RequestException as exc:
            return PaymentResult(
                success=False,
                error=f'Connection error: {exc}',
                gateway=self.name
            )
        except Exception as exc:
            return PaymentResult(
                success=False,
                error=f'Unexpected error: {exc}',
                gateway=self.name
            )


class PaymentGatewayService:
    """سرویس مدیریت درگاه پرداخت (فقط سپهر)"""

    @staticmethod
    def get_gateway() -> SepehrPaymentGateway:
        gateways_config = getattr(settings, 'PAYMENT_GATEWAYS', {})
        sepehr_config = gateways_config.get('sepehr', {})
        return SepehrPaymentGateway(name='sepehr', config=sepehr_config)

    @classmethod
    def create_payment_request(
        cls,
        amount: Decimal,
        description: str,
        callback_url: str,
        user_phone: Optional[str] = None,
        user_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            provider = cls.get_gateway()
            result = provider.create_payment_request(
                amount=amount,
                description=description,
                callback_url=callback_url,
                user_phone=user_phone,
                user_email=user_email,
                metadata=metadata,
            )
            return asdict(result)
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc),
                'gateway': 'sepehr'
            }

    @classmethod
    def verify_payment(
        cls,
        authority: str,
        amount: Decimal,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            provider = cls.get_gateway()
            result = provider.verify_payment(
                authority=authority,
                amount=amount,
                metadata=metadata,
            )
            return asdict(result)
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc),
                'gateway': 'sepehr'
            }

