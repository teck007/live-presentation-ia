"""Cliente LLM, para llamar a la API de Meta."""

import os
import time
import dotenv
from openai import OpenAI

dotenv.load_dotenv()

client = OpenAI(
    base_url="https://api.meta.ai/v1",
    api_key=os.getenv("MODEL_API_KEY"),
)
def analyze_text(text: str) -> str:
    """Analyze the text using the LLM model.

    Args:
        text (str): The text to analyze.

    Returns:
        str: The analysis of the input text."""
    start = time.perf_counter()
    response = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[
            {"role": "system", "content": "Responde en máximo 30 palabras o 1-2 frases. Sé directo. Explicación simple y concisa, no uses listas a menos que te lo pidan. Solo español."},
            {"role": "user", "content": text}
                ],
        temperature=0.3,
        top_p=0.9,
        max_completion_tokens=2000,
        reasoning_effort="minimal",
    )
    elapsed = time.perf_counter() - start
    print(f"[llm] analyze_text tomó {elapsed:.2f}s")
    return response.choices[0].message.content


if __name__ == "__main__":
    response = analyze_text("Python")
    print(response)
