"""Provider registry — maps provider name strings to provider instances."""
from app.providers.base import BaseWeatherProvider
from app.providers.open_meteo import OpenMeteoProvider
from app.providers.google_weather import GoogleWeatherProvider

_REGISTRY: dict[str, BaseWeatherProvider] = {
    "open_meteo": OpenMeteoProvider(),
    "google_weather": GoogleWeatherProvider(),
}


def get_provider(name: str) -> BaseWeatherProvider:
    """
    Return the provider instance for the given name.
    Raises KeyError if the provider is not registered.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(_REGISTRY.keys())
        raise KeyError(f"Unknown provider {name!r}. Available: {available}")


def list_providers() -> list[str]:
    """Return all registered provider names."""
    return list(_REGISTRY.keys())
