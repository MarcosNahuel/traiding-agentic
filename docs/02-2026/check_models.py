from google import genai

client = genai.Client(api_key="AIzaSyDFzEqrAAa1kgHQ8GS9pZEXdtvDj02_VF4")

for m in client.models.list():
    name = m.name
    if "image" in name.lower() or "flash" in name.lower() or "pro" in name.lower() or "imagen" in name.lower():
        methods = getattr(m, 'supported_generation_methods', [])
        print(f"{name} -> {methods}")
