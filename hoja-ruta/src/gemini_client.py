from __future__ import annotations

from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, GEMINI_MODEL


DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


def get_gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise ValueError(
            "No se encontro GEMINI_API_KEY. Crea un archivo .env en la raiz del proyecto."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def get_model_name() -> str:
    return GEMINI_MODEL or DEFAULT_GEMINI_MODEL


def _supports_generate_content(model) -> bool:
    supported_actions = getattr(model, "supported_actions", None) or []
    supported_methods = getattr(model, "supported_generation_methods", None) or []
    capabilities = {str(item) for item in [*supported_actions, *supported_methods]}
    return "generateContent" in capabilities or "generate_content" in capabilities


def list_available_models() -> list[str]:
    """Devuelve modelos disponibles que soportan generateContent."""
    client = get_gemini_client()
    models: list[str] = []

    for model in client.models.list():
        model_name = getattr(model, "name", "")
        if model_name and _supports_generate_content(model):
            models.append(model_name)

    return models


def print_available_models() -> None:
    models = list_available_models()
    if not models:
        print("No se encontraron modelos disponibles para generateContent.")
        return

    print("Modelos disponibles para generateContent:")
    for model_name in models:
        print(f"- {model_name}")


def generate_text(prompt: str) -> str:
    client = get_gemini_client()
    model_name = get_model_name()

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
            ),
        )
    except Exception as exc:
        message = str(exc)
        if "404" in message or "not found" in message.lower():
            raise RuntimeError(
                "El modelo configurado no esta disponible. Revisa GEMINI_MODEL en .env "
                "o ejecuta el listado de modelos disponibles."
            ) from exc
        raise RuntimeError(f"Gemini no pudo generar la respuesta: {exc}") from exc

    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise ValueError("Gemini devolvio una respuesta vacia.")
    return text


if __name__ == "__main__":
    try:
        print_available_models()
    except Exception as exc:
        print(f"ERROR - {exc}")
        raise SystemExit(1) from exc
