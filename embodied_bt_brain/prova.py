from openai import AzureOpenAI
import base64, keys

image_path = "dataset1/dlr_edan_shared_control_converted_externally_to_rlds_0.1.0/episode_000/contact_sheet.jpg"
prompt_path = "/home/kcbat/LM T2I/oxe-bt-pipeline/dataset1/dlr_edan_shared_control_converted_externally_to_rlds_0.1.0/episode_000/prompt.md"

client = AzureOpenAI(
    api_key=keys.AZURE_OPENAI_KEY,
    azure_endpoint=keys.AZURE_OPENAI_ENDPOINT,
    api_version=keys.AZURE_OPENAI_API_VERSION,
)

# Chiamata al modello multimodale
resp = client.chat.completions.create(
    model="gpt-5",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Ciao, rispondi con un Hello World"},
            ]
        }
    ]
)

print(resp.choices[0].message.content)
