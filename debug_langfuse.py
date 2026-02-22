
try:
    import langfuse
    print(f"Langfuse Version: {langfuse.version.__version__}")
    from langfuse import Langfuse
    client = Langfuse()
    print(f"Client Methods: {dir(client)}")
except Exception as e:
    print(f"Error: {e}")
