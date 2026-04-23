from typing import Dict, Any
import re


class IntentClassifier:
    """Classifies user intent from messages"""
    
    def __init__(self):
        # Define intent keywords for different languages
        self.intent_keywords = {
            "book": {
                "en": ["book", "schedule", "appointment", "make an appointment", "i need an appointment", "want to book"],
                "hi": ["बुक", "अपॉइंटमेंट", "नियुक्त", "समय", "मिलना"],
                "ta": ["புக்", "நியமனம்", "சந்திப்பு", "நேரம்"]
            },
            "reschedule": {
                "en": ["reschedule", "change", "different time", "move", "another day", "postpone"],
                "hi": ["पुनः निर्धारित", "बदलना", "दूसरा समय", "स्थगित"],
                "ta": ["மாற்று", "வேறு நேரம்", "பின்னர்", "தள்ளுபடி"]
            },
            "cancel": {
                "en": ["cancel", "delete", "remove", "don't need", "no longer", "forget it"],
                "hi": ["रद्द", "हटाना", "नहीं चाहिए", "आवश्यकता नहीं"],
                "ta": ["ரத்து", "வேண்டாம்", "தேவை இல்லை"]
            },
            "query": {
                "en": ["how", "what", "when", "which", "tell me", "information", "available", "doctor"],
                "hi": ["कैसे", "क्या", "कौन", "बताएं", "जानकारी", "डॉक्टर"],
                "ta": ["எப்படி", "என்ன", "யார்", "சொல்லு", "தகவல்", "வைத்தியர்"]
            },
            "confirm": {
                "en": ["confirm", "yes", "ok", "okay", "that's correct", "sounds good"],
                "hi": ["पुष्टि", "हाँ", "ठीक है", "सही है"],
                "ta": ["உறுதி", "ஆம்", "சரி"]
            }
        }
        
        print("[v0] IntentClassifier initialized")
    
    def classify(self, message: str, language: str = "en") -> Dict[str, Any]:
        """
        Classify user intent from message
        
        Returns:
            {
                "intent": "book|reschedule|cancel|query|confirm",
                "confidence": 0-100,
                "keywords_found": [...]
            }
        """
        
        message_lower = message.lower().strip()
        scores = {}
        keywords_found = {intent: [] for intent in self.intent_keywords}
        
        # Score each intent based on keyword matches
        for intent, lang_keywords in self.intent_keywords.items():
            keywords = lang_keywords.get(language, lang_keywords.get("en", []))
            
            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
                    keywords_found[intent].append(keyword)
            
            scores[intent] = score
        
        # Get the intent with highest score
        max_score = max(scores.values()) if scores else 0
        
        if max_score == 0:
            # Default to query if no keywords found
            classified_intent = "query"
            confidence = 30
        else:
            classified_intent = max(scores, key=scores.get)
            # Calculate confidence (0-100)
            confidence = min(100, max_score * 25)  # Each keyword = 25% confidence
        
        print(f"[v0] Intent classified: {classified_intent} (confidence: {confidence})")
        
        return {
            "intent": classified_intent,
            "confidence": confidence,
            "keywords_found": keywords_found[classified_intent],
            "all_scores": scores
        }
