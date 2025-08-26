from keys import get_openai_client, default_model
import os
print("ENV CHECK:", {k: bool(os.getenv(k)) for k in [
    "OPENAI_PROVIDER","AZURE_OPENAI_API_KEY","AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION","AZURE_OPENAI_CHAT_DEPLOYMENT"]})
client = get_openai_client()
print("Model:", default_model())
resp = client.chat.completions.create(
    model=default_model(),
    messages=[{"role":"user","content":"scrivi 'ok'"}],
    temperature=0.0,
)
print("Reply:", resp.choices[0].message.content)
