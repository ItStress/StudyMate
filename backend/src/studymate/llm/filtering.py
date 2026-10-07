import re


def answer_without_thinking(content: str) -> str:
    """Keep visible text, including models that omit the opening think tag."""
    visible: list[str] = []
    depth = 0
    for part in re.split(r"(<\s*/?\s*think\s*>)", content, flags=re.IGNORECASE):
        if re.fullmatch(r"<\s*think\s*>", part, flags=re.IGNORECASE):
            depth += 1
        elif re.fullmatch(r"<\s*/\s*think\s*>", part, flags=re.IGNORECASE):
            if depth:
                depth -= 1
            else:
                visible.clear()
        elif depth == 0:
            visible.append(part)
    return "".join(visible).strip()


class StreamingAnswerFilter:
    """Suppress tagged thinking even when tags span multiple Ollama chunks."""

    def __init__(self) -> None:
        self.pending = ""
        self.depth = 0
        self.started = False
        self.can_start = True
        self.closed = False
        self.raw = ""

    def feed(self, text: str, *, final: bool = False) -> str:
        self.pending += text
        if not self.started:
            self.raw += text
        output: list[str] = []
        while self.pending:
            if self.pending.startswith("<"):
                end = self.pending.find(">")
                if end == -1:
                    if not final:
                        break
                    # Never expose an unfinished thinking marker.
                    if re.match(r"<\s*/?\s*t(?:h(?:i(?:n(?:k)?)?)?)?\s*$", self.pending, re.I):
                        self.pending = ""
                        break
                    end = len(self.pending) - 1
                part, self.pending = self.pending[:end + 1], self.pending[end + 1:]
                if re.fullmatch(r"<\s*think\s*>", part, re.I):
                    self.depth += 1
                elif re.fullmatch(r"<\s*/\s*think\s*>", part, re.I):
                    if self.depth:
                        self.depth -= 1
                    elif self.started and not self.closed:
                        raise ValueError("Unmatched thinking marker")
                    if not self.depth:
                        # An omitted opening <think> tag is common in legacy output.
                        # Only its closing tag establishes a new answer boundary.
                        self.can_start = True
                elif not self.depth and self.can_start and not self.started and re.fullmatch(r"<answer>", part, re.I):
                    self.started = True
                    self.raw = ""
                elif not self.depth and self.started and re.fullmatch(r"</answer>", part, re.I):
                    self.closed = True
                elif not self.depth:
                    if self.started and not self.closed:
                        output.append(part)
                    elif not self.started:
                        self.can_start = False
            else:
                end = self.pending.find("<")
                if end == -1:
                    end = len(self.pending)
                part, self.pending = self.pending[:end], self.pending[end:]
                if not self.depth:
                    if self.started and not self.closed:
                        output.append(part)
                    elif not self.started and part.strip():
                        # A marker quoted in a sentence is not an answer boundary.
                        self.can_start = False
        if final and not self.started:
            # Older models may put untagged reasoning before </think>. Buffer until
            # completion rather than expose it while waiting for the answer marker.
            return answer_without_thinking(self.raw)
        return "".join(output)
