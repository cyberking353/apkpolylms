import re
from typing import List, Tuple, Optional

CSRF_RE = re.compile(rb'<input[^>]*name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']')


def extract_csrf(html: bytes) -> Optional[str]:
    m = CSRF_RE.search(html)
    return m.group(1).decode() if m else None


def extract_question_ids(html: bytes) -> List[Tuple[int, List[int]]]:
    pattern = re.compile(rb'name=["\']question_(\d+)["\'].*?value=["\'](\d+)["\']')
    q_map = {}
    for m in pattern.finditer(html):
        qid = int(m.group(1))
        cid = int(m.group(2))
        q_map.setdefault(qid, []).append(cid)
    return [(qid, choices) for qid, choices in q_map.items()]


def extract_session_token(html: bytes) -> Optional[str]:
    m = re.search(rb'const SESSION_TOKEN\s*=\s*"([^"]+)"', html)
    return m.group(1).decode() if m else None


def extract_attempt_id(html: bytes) -> Optional[int]:
    m = re.search(rb'/exams/result/(\d+)/', html)
    return int(m.group(1)) if m else None
