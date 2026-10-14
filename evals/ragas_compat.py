"""Import ragas despite a dependency skew.

ragas 0.4.3 imports `langchain_community.chat_models.vertexai.ChatVertexAI`, which was removed in
langchain-community 0.4.x (the version that matches langchain 1.x). ragas only uses the class in an
`isinstance` allowlist, so a placeholder class is enough. Remove this once ragas drops the import.
"""

import sys
import types


def import_ragas():
    name = "langchain_community.chat_models.vertexai"
    if name not in sys.modules:
        try:
            __import__(name)
        except ModuleNotFoundError:
            stub = types.ModuleType(name)
            stub.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules[name] = stub
    import ragas

    return ragas
