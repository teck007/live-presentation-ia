import os
import dotenv
from openai import OpenAI

dotenv.load_dotenv()

client = OpenAI(
    base_url="https://api.meta.ai/v1",
    api_key=os.getenv("MODEL_API_KEY"),
)

response = client.models.list()

print(response.model_dump_json(indent=2))


"""
model = "meta-llama/Llama-3.2-3B-Instruct"

temperature = 0.3      # 0.2 a 0.5 = directo, no inventa ni divaga
top_p = 0.9
max_tokens = 80        # LA CLAVE: 60-120 para respuestas cortas. No pongas 500 o 1000
stream = True          # para que parezca instantáneo
stop = ["\n\n", "Usuario:"]
"""