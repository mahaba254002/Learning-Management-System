"""Africa's Talking SMS client (standard library only) and SMS length rules.

Send: POST /version1/messaging with username, to, message and optional from,
authenticated by the apiKey header. Each recipient in the reply has a statusCode
(101 means accepted), a messageId used by delivery reports, and a cost string
such as "KES 0.8000"."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from app.core.config import settings

HOSTS = {'sandbox': 'https://api.sandbox.africastalking.com', 'production': 'https://api.africastalking.com'}
GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
GSM7_EXTENDED = set("^{}\\[~]|€")
ACCEPTED = {100, 101, 102}


class SmsError(Exception):
    pass


def configured():
    return bool(settings.AT_USERNAME and settings.AT_API_KEY)


def parts(text):
    """SMS parts a text needs: 160/153 characters in the GSM alphabet, 70/67 otherwise."""
    if not text:
        return 0
    if all(ch in GSM7 or ch in GSM7_EXTENDED for ch in text):
        length = sum(2 if ch in GSM7_EXTENDED else 1 for ch in text)
        return 1 if length <= 160 else -(-length // 153)
    length = len(text.encode('utf-16-le')) // 2
    return 1 if length <= 70 else -(-length // 67)


def cost(value):
    match = re.search(r'([0-9]+(?:\.[0-9]+)?)', value or '')
    try:
        return Decimal(match.group(1)) if match else None
    except InvalidOperation:
        return None


def send(numbers, message):
    """Send one text to up to 100 numbers. Returns {number: {accepted, message_id, cost, status}}."""
    if not configured():
        raise SmsError('SMS is not set up')
    data = dict(username=settings.AT_USERNAME, to=','.join(numbers), message=message)
    if settings.AT_SENDER_ID:
        data['from'] = settings.AT_SENDER_ID
    request = urllib.request.Request(f"{HOSTS[settings.AT_ENVIRONMENT]}/version1/messaging", data=urllib.parse.urlencode(data).encode(),
                                     headers={'apiKey': settings.AT_API_KEY, 'Accept': 'application/json',
                                              'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode() or '{}')
    except urllib.error.HTTPError as exc:
        raise SmsError(f'Provider refused the request ({exc.code})') from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SmsError('Could not reach the SMS provider') from exc
    result = {}
    for item in body.get('SMSMessageData', {}).get('Recipients', []):
        code = item.get('statusCode')
        result[item.get('number')] = dict(accepted=code in ACCEPTED, message_id=item.get('messageId'),
                                          cost=cost(item.get('cost')), status=item.get('status') or '')
    return result
