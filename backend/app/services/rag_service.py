class RAGService:
    """Converts raw MongoDB documents into a plain-text context string.

    Single responsibility: formatting. No MongoDB access, no API calls.
    Each domain has its own builder that knows that domain's field schema.
    """

    @staticmethod
    def build_weather_context(records: list) -> str:
        if not records:
            return "No relevant weather data found for the given query."

        lines = ["=== Historical Weather Data (India) ==="]
        for r in records:
            parts = [
                f"City: {r.get('city', 'N/A')}",
                f"Date: {r.get('date', 'N/A')}",
                f"Temperature (mean): {r.get('temperature', 'N/A')}°C",
                f"Temperature (max): {r.get('temperature_max', 'N/A')}°C",
                f"Temperature (min): {r.get('temperature_min', 'N/A')}°C",
                f"Humidity: {r.get('humidity', 'N/A')}%",
                f"Wind Speed: {r.get('wind_speed', 'N/A')} km/h",
                f"Condition: {r.get('condition', 'N/A')}",
            ]
            if r.get("rainfall_mm") is not None:
                parts.append(f"Rainfall: {r['rainfall_mm']} mm")
            lines.append("  " + " | ".join(parts))

        return "\n".join(lines)

    @staticmethod
    def build_stock_context(records: list) -> str:
        if not records:
            return "No relevant stock data found for the given query."

        lines = ["=== Historical Stock Data (Indian Market / NSE) ==="]
        for r in records:
            parts = [
                f"Company: {r.get('company', 'N/A')}",
                f"Symbol: {r.get('symbol', 'N/A')}",
                f"Date: {r.get('date', 'N/A')}",
                f"Open: ₹{r.get('open', 'N/A')}",
                f"High: ₹{r.get('high', 'N/A')}",
                f"Low: ₹{r.get('low', 'N/A')}",
                f"Close: ₹{r.get('close', 'N/A')}",
                f"Volume: {r.get('volume', 'N/A')} shares",
                f"Change: {r.get('change_percent', 'N/A')}%",
            ]
            lines.append("  " + " | ".join(parts))

        return "\n".join(lines)

    @staticmethod
    def build_news_context(records: list) -> str:
        if not records:
            return "No relevant news data found for the given query."

        lines = ["=== Historical Indian News ==="]
        for r in records:
            parts = [
                f"Date: {r.get('date', 'N/A')}",
                f"Category: {r.get('category', 'N/A')}",
                f"Source: {r.get('source', 'N/A')}",
                f"Title: {r.get('title', 'N/A')}",
            ]
            if r.get("summary"):
                parts.append(f"Summary: {r['summary']}")
            lines.append("  " + " | ".join(parts))

        return "\n".join(lines)
