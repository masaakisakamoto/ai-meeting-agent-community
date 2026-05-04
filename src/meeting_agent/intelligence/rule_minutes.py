from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from meeting_agent.core.schemas import (
    ActionItem,
    Decision,
    MinutesDraft,
    OpenQuestion,
    Risk,
    TopicBlock,
    Transcript,
    TranscriptSegment,
)
from meeting_agent.core.transcript import split_sentences

DECISION_KEYWORDS = (
    "決定",
    "決まり",
    "決めます",
    "合意",
    "採用",
    "承認",
    "方針で合意",
    "方針とします",
    "方針にします",
    "進めることで",
    "進めましょう",
    "確定",
)
ACTION_KEYWORDS = (
    "お願いします",
    "お願い",
    "対応",
    "確認",
    "作成",
    "調査",
    "実装",
    "レビュー",
    "共有",
    "送付",
    "準備",
    "担当",
    "やります",
    "進めます",
)
QUESTION_KEYWORDS = (
    "？",
    "?",
    "どうする",
    "どうしましょう",
    "未定",
    "検討",
    "確認が必要",
    "論点",
    "課題",
)
RISK_KEYWORDS = (
    "リスク",
    "懸念",
    "問題",
    "ブロッカー",
    "遅れ",
    "難しい",
    "危険",
    "不安",
)
DUE_PATTERNS = (
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
    r"\d{1,2}月\d{1,2}日(?:まで|迄)?",
    r"(?:今日|本日|明日|明後日|今週中|来週中|月末|週明け|午前中|午後|今月中|来月中)(?:まで|迄)?",
    r"(?:月曜|火曜|水曜|木曜|金曜|土曜|日曜)(?:日)?(?:まで|迄)?",
)


@dataclass
class RuleBasedMinutesGenerator:
    """Baseline generator.

    The private/commercial Quality Engine can implement the same `generate` method
    with LLM orchestration, term correction, model routing, and deeper verification.
    """

    max_summary_segments: int = 5

    def generate(self, transcript: Transcript, template_id: str = "default") -> MinutesDraft:
        transcript.sort_segments()
        decisions: list[Decision] = []
        actions: list[ActionItem] = []
        questions: list[OpenQuestion] = []
        risks: list[Risk] = []

        seen_decisions: set[str] = set()
        seen_actions: set[str] = set()
        seen_questions: set[str] = set()
        seen_risks: set[str] = set()

        for segment in transcript.segments:
            for sentence in split_sentences(segment.text):
                compact = _clean_item_text(sentence)
                key = _dedupe_key(compact)
                if _contains_any(compact, DECISION_KEYWORDS) and key not in seen_decisions:
                    seen_decisions.add(key)
                    decisions.append(
                        Decision(
                            id=f"dec_{len(decisions)+1:03d}",
                            text=_normalize_decision(compact),
                            confidence=_confidence(compact, DECISION_KEYWORDS),
                            evidence_segment_ids=[segment.id],
                            rationale="decision keyword matched",
                        )
                    )
                if _is_action_sentence(compact) and key not in seen_actions:
                    seen_actions.add(key)
                    actions.append(
                        ActionItem(
                            id=f"act_{len(actions)+1:03d}",
                            task=_extract_task(compact),
                            owner=_extract_owner(compact, segment),
                            due_date=_extract_due_date(compact),
                            confidence=_confidence(compact, ACTION_KEYWORDS),
                            evidence_segment_ids=[segment.id],
                            rationale="action keyword matched",
                        )
                    )
                if _contains_any(compact, QUESTION_KEYWORDS) and key not in seen_questions:
                    seen_questions.add(key)
                    questions.append(
                        OpenQuestion(
                            id=f"q_{len(questions)+1:03d}",
                            text=compact,
                            owner=_extract_owner(compact, segment, fallback="未定"),
                            confidence=_confidence(compact, QUESTION_KEYWORDS),
                            evidence_segment_ids=[segment.id],
                            rationale="question/open issue keyword matched",
                        )
                    )
                if _contains_any(compact, RISK_KEYWORDS) and key not in seen_risks:
                    seen_risks.add(key)
                    risks.append(
                        Risk(
                            id=f"risk_{len(risks)+1:03d}",
                            text=compact,
                            severity=_risk_severity(compact),
                            confidence=_confidence(compact, RISK_KEYWORDS),
                            evidence_segment_ids=[segment.id],
                            rationale="risk keyword matched",
                        )
                    )

        topics = _build_topic_blocks(transcript)
        summary = _build_summary(transcript, decisions, actions, questions, risks)
        return MinutesDraft(
            meeting_id=transcript.meeting_id,
            title=transcript.title,
            summary=summary,
            decisions=decisions,
            action_items=actions,
            open_questions=questions,
            risks=risks,
            topics=topics,
            generator="rule-based-community-ja-v0.1",
            metadata={"template_id": template_id},
        )


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(k in text for k in keywords)


def _is_action_sentence(text: str) -> bool:
    if not _contains_any(text, ACTION_KEYWORDS):
        return False
    # Avoid classifying every "確認が必要" as a concrete action unless a person or deadline exists.
    if "確認が必要" in text and not (_extract_due_date(text) != "未定" or re.search(r"担当|さん|私が|僕が|自分が", text)):
        return False
    return True


def _clean_item_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" 。\n\t"))


def _dedupe_key(text: str) -> str:
    return re.sub(r"[\s。、,.!?！？]", "", text).lower()[:80]


def _confidence(text: str, keywords: Sequence[str]) -> float:
    hits = sum(1 for k in keywords if k in text)
    score = 0.55 + min(hits, 3) * 0.12
    if _extract_due_date(text) != "未定":
        score += 0.08
    if re.search(r"担当|さん|私が|僕が|自分が", text):
        score += 0.08
    return round(min(score, 0.95), 2)


def _normalize_decision(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^(では|じゃあ|それでは)[、\s]*", "", text)
    return text


def _extract_due_date(text: str) -> str:
    for pattern in DUE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            due = match.group(0)
            return due.rstrip("まで迄") + ("まで" if "まで" in due or "迄" in due else "")
    return "未定"


def _extract_owner(text: str, segment: TranscriptSegment, fallback: str = "未定") -> str:
    if re.search(r"(私|わたし|僕|自分)が", text):
        return segment.speaker_name if segment.speaker_name != "Unknown" else fallback
    patterns = [
        r"担当(?:は|者は)?\s*(?P<name>[一-龯ぁ-んァ-ヶA-Za-z][一-龯ぁ-んァ-ヶA-Za-z0-9・_\-]{0,12})",
        r"(?P<name>[一-龯ぁ-んァ-ヶA-Za-z][一-龯ぁ-んァ-ヶA-Za-z0-9・_\-]{0,12})さん[、,\s].*(?:お願い|対応|確認|作成|調査|実装|レビュー|共有|準備)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group("name")
            if name not in {"来週", "今週", "今日", "明日", "本日"}:
                return name
    return fallback


def _extract_task(text: str) -> str:
    task = text.strip()
    task = re.sub(r"^[一-龯ぁ-んァ-ヶA-Za-z0-9・_\-]{1,16}さん[、,\s]*", "", task)
    task = re.sub(r"^(私が|わたしが|僕が|自分が)", "", task)
    task = re.sub(r"お願いします[。.]?$", "", task)
    task = re.sub(r"お願い[。.]?$", "", task)
    task = task.strip(" 。")
    return task or text.strip()


def _risk_severity(text: str) -> str:
    if any(k in text for k in ("重大", "危険", "停止", "致命", "大きい")):
        return "high"
    if any(k in text for k in ("軽微", "小さい", "低い")):
        return "low"
    return "medium"


def _build_topic_blocks(transcript: Transcript) -> list[TopicBlock]:
    if not transcript.segments:
        return []
    # Very simple block: first 30 minutes per block. Replaceable by private topic segmentation.
    blocks: dict[int, list[TranscriptSegment]] = {}
    for s in transcript.segments:
        bucket = s.start_ms // (30 * 60 * 1000)
        blocks.setdefault(bucket, []).append(s)
    out = []
    for bucket, segs in sorted(blocks.items()):
        title = "全体" if len(blocks) == 1 else f"パート {bucket + 1}"
        summary_text = " / ".join(s.compact_quote(50) for s in segs[:3])
        out.append(TopicBlock(title=title, summary=summary_text, evidence_segment_ids=[s.id for s in segs[:3]]))
    return out


def _build_summary(
    transcript: Transcript,
    decisions: Sequence[Decision],
    actions: Sequence[ActionItem],
    questions: Sequence[OpenQuestion],
    risks: Sequence[Risk],
) -> str:
    if not transcript.segments:
        return "発言ログがありません。"
    speakers = sorted({s.speaker_name for s in transcript.segments if s.speaker_name != "Unknown"})
    parts = [
        f"全{len(transcript.segments)}件の発言から、決定事項{len(decisions)}件、ToDo{len(actions)}件、未解決論点{len(questions)}件、リスク{len(risks)}件を抽出しました。"
    ]
    if speakers:
        parts.append("主な参加者: " + "、".join(speakers) + "。")
    first = transcript.segments[0].compact_quote(80)
    parts.append(f"冒頭では「{first}」という流れから議論が始まりました。")
    return "".join(parts)
