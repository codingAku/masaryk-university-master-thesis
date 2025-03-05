import subprocess

# -----------------------------
# 1. Get available models via ollama list command.
# -----------------------------
def get_available_models():
    try:
        output = subprocess.check_output(["ollama", "list"], universal_newlines=True)
        models = []
        for line in output.splitlines():
            if line.strip() and not line.startswith("NAME"):
                models.append(line.strip().split()[0])
        return models if models else ["llama3.1:latest"]
    except Exception as e:
        return ["llama3.1:latest"]
