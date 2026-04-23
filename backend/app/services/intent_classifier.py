from typing import Dict, Any


class IntentClassifier:
    """Lightweight fallback intent classifier"""

    def __init__(self):
        self.intent_keywords = {
            "book": {
                "en": [
                    "book", "schedule", "appointment", "make an appointment",
                    "need appointment", "want to book"
                ],
            },
            "reschedule": {
                "en": [
                    "reschedule", "change", "move", "another time",
                    "another day", "postpone"
                ],
            },
            "cancel": {
                "en": [
                    "cancel", "delete", "remove", "don't need", "no longer"
                ],
            },
            "query": {
                "en": [
                    "how", "what", "when", "which", "available", "doctor", "slot"
                ],
            },
        }

        print("[v0] IntentClassifier initialized")

    def classify(self, message: str, language: str = "en") -> Dict[str, Any]:
        message_lower = message.lower().strip()
        scores = {}
        keywords_found = {intent: [] for intent in self.intent_keywords}

        for intent, lang_keywords in self.intent_keywords.items():
            keywords = lang_keywords.get(language, lang_keywords.get("en", []))

            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
                    keywords_found[intent].append(keyword)

            scores[intent] = score

        max_score = max(scores.values()) if scores else 0

        if max_score == 0:
            classified_intent = "query"
            confidence = 30
        else:
            classified_intent = max(scores, key=scores.get)
            confidence = min(100, 40 + max_score * 20)

        print(f"[v0] Intent classified: {classified_intent} (confidence: {confidence})")

        return {
            "intent": classified_intent,
            "confidence": confidence,
            "keywords_found": keywords_found[classified_intent],
            "all_scores": scores,
        }