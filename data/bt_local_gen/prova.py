from openai import AzureOpenAI
import base64, keys

image_path = "dataset1/dlr_edan_shared_control_converted_externally_to_rlds_0.1.0/episode_000/contact_sheet.jpg"
prompt_path = "/home/kcbat/LM T2I/oxe-bt-pipeline/dataset1/dlr_edan_shared_control_converted_externally_to_rlds_0.1.0/episode_000/prompt.md"

client = AzureOpenAI(
    api_key=keys.azure_openai_key,
    azure_endpoint=keys.azure_openai_endpoint,
    api_version=keys.azure_openai_api_version,
)

# Codifica immagine in base64
with open(image_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

# Legge il testo del prompt
with open(prompt_path, "r") as f:
    prompt_text = f.read()

# Chiamata al modello multimodale
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        }
    ]
)

print(resp.choices[0].message.content)
