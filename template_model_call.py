from openai import OpenAI
import json
import os


# If running from workbench use /tmp/jwt. Otherwise provide your CDP_TOKEN
API_KEY = json.load(open("/tmp/jwt"))["access_token"]

# Endpoint and model come from environment variables, e.g.
#   CAI_BASE_URL=https://<domain>/namespaces/serving-default/endpoints/<endpoint>/openai/v1
#   CAI_MODEL=Qwen/Qwen2.5-7B-Instruct
MODEL_ID = os.environ["CAI_MODEL"]

client = OpenAI(
	base_url=os.environ["CAI_BASE_URL"],
	api_key=API_KEY,
)

completion = client.chat.completions.create(
	model=MODEL_ID,
	messages=[{"role": "user", "content": "Write a one-sentence definition of GenAI."}],
	temperature=0.2,
	top_p=0.7,
	max_tokens=1024,
	stream=True
)

for chunk in completion:
	if chunk.choices[0].delta.content is not None:
		print(chunk.choices[0].delta.content, end="")
