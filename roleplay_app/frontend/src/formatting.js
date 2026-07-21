function extractQuotedDialogue(actionText) {
  const quoteRegex = /["“][^"”]*["”]/g;
  const segments = [];
  let lastIndex = 0;
  let match;

  while ((match = quoteRegex.exec(actionText)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "action", text: actionText.slice(lastIndex, match.index) });
    }
    segments.push({ type: "dialogue", text: match[0] });
    lastIndex = quoteRegex.lastIndex;
  }
  if (lastIndex < actionText.length) {
    segments.push({ type: "action", text: actionText.slice(lastIndex) });
  }
  return segments;
}

export function parseFormattedText(text) {
  const regex = /\*([^*]+)\*|\(([^)]+)\)/g;
  const rawSegments = [];
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      rawSegments.push({ type: "dialogue", text: text.slice(lastIndex, match.index) });
    }
    if (match[1] !== undefined) {
      rawSegments.push({ type: "action", text: match[1] });
    } else {
      rawSegments.push({ type: "monologue", text: match[2] });
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    rawSegments.push({ type: "dialogue", text: text.slice(lastIndex) });
  }

  // Models sometimes wrap an entire turn (narration + spoken dialogue) in a single pair of
  // asterisks instead of closing/reopening around the dialogue, as instructed. Quoted text is
  // a reliable signal for actual speech regardless of asterisk placement, so pull it back out
  // of any "action" segment and render it as plain dialogue.
  const segments = [];
  for (const seg of rawSegments) {
    if (seg.type === "action") {
      segments.push(...extractQuotedDialogue(seg.text));
    } else {
      segments.push(seg);
    }
  }
  return segments;
}
