"""
Email parsing & normalization layer — wrapper di atas classifier EmailParser.

Memastikan setiap email yang masuk memiliki format standar sebelum masuk pipeline.
"""

from classifier.features import EmailParser as ClassifierEmailParser, ParsedEmail


class IngestionEmailParser:
    def __init__(self):
        self._parser = ClassifierEmailParser()

    def parse(self, raw_email_str: str) -> ParsedEmail:
        return self._parser.parse(raw_email_str)

    def normalize(self, parsed: ParsedEmail) -> ParsedEmail:
        parsed.sender = parsed.sender.lower().strip()
        parsed.subject = parsed.subject.strip()
        if parsed.subject.upper().startswith("RE:"):
            parsed.subject = parsed.subject[3:].strip()
        elif parsed.subject.upper().startswith("FWD:"):
            parsed.subject = parsed.subject[4:].strip()
        elif parsed.subject.upper().startswith("FW:"):
            parsed.subject = parsed.subject[3:].strip()
        return parsed
