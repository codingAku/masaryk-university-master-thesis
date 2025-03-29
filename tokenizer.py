import nltk
import re
from nltk.tokenize import sent_tokenize
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')
    
PAREN_REGEX = re.compile(r'\([^)]*\)')

def chunk_text(text, max_tokens=18, tokenizer=None):
    """
    Splits text into chunks with each chunk containing at most max_tokens tokens.
    First splits text into sentences, and if a sentence is too long, splits it by words.
    
    Args:
      text (str): The text to split.
      max_tokens (int): The maximum number of tokens per chunk.
      tokenizer (callable, optional): A function that returns tokens from a string.
                                      If not provided, splits on whitespace.
    Returns:
      List[str]: List of text chunks.
    """
    sentences = sent_tokenize(remove_parentheses(text))
    chunks = []
    current_chunk = []
    current_count = 0

    for sentence in sentences:
        if tokenizer:
            sentence_tokens = tokenizer(sentence)
        else:
            sentence_tokens = sentence.split()
        sentence_token_count = len(sentence_tokens)

        if sentence_token_count > max_tokens:
            # Sentence is too long; split it further into words and form sub-chunks.
            words = sentence_tokens
            for i in range(0, len(words), max_tokens):
                sub_chunk = " ".join(words[i:i + max_tokens])
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_count = 0
                chunks.append(sub_chunk)
        else:
            if current_count + sentence_token_count > max_tokens:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_count = sentence_token_count
            else:
                current_chunk.append(sentence)
                current_count += sentence_token_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def remove_parentheses(text: str) -> str:
  return PAREN_REGEX.sub('', text)


# Example usage:
text = "uh... Concentration curve computation, And the optical emission spectrometer ticket I think I remember now.  I'm afraid I'm not quite sure about this part. Could you explain a bit more?"
chunks = chunk_text(text, max_tokens=18)
for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}: {chunk}")
