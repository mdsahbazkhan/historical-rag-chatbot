# Historical Multi-Domain RAG Chatbot

A production-quality full-stack AI chatbot that answers questions about historical Indian **Weather**, **Stock Market**, and **News** data using a hand-rolled Retrieval-Augmented Generation (RAG) pipeline — no LangChain, no vector database.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Axios, CSS |
| Backend | FastAPI, Python 3.12, Pydantic |
| Database | MongoDB Atlas (PyMongo) |
| AI / LLM | Google Gemini (`gemini-3-flash-preview`) |
| Weather Data | Open-Meteo Archive API (free, no key) |
| Stock Data | Yahoo Finance Chart API (free, no key) |
| News Data | The Guardian Open Platform API (free key) |

---

## Architecture

```
React Frontend
     │
     │  POST /api/chat  { mode, question }
     ▼
FastAPI Router  (app/routers/chat.py)
     │
     ▼
ChatService  — validates mode, dispatches, saves to chat_history
     │
     ├── mode=weather ──► WeatherService
     ├── mode=stock   ──► StockService
     └── mode=news    ──► NewsService
              │
              │  1. Extract city / company / keywords + date range from question
              │  2. Query MongoDB with targeted filters
              ▼
        MongoDB Atlas
        ┌─────────────────┐
        │  weather_data   │  10 cities × 5 years (~18,000 records)
        │  stock_data     │  15 NSE stocks × 5 years (~15,000 records)
        │  news_data      │  India articles × 2 years (~3,000 articles)
        │  chat_history   │  every exchange persisted
        └─────────────────┘
              │
              │  3. Retrieved records → RAGService (format context string)
              ▼
        RAGService  (app/services/rag_service.py)
              │
              │  4. context + question → GeminiService
              ▼
        GeminiService  (app/services/gemini_service.py)
              │
              │  5. Gemini generates answer grounded only in context
              ▼
     { "answer": "..." }
```

---

## RAG Pipeline — How It Works

**Retrieve → Augment → Generate** without any vector database:

1. **Extract** — each service parses the user question using regex to extract:
   - Weather: city name (matched against known Indian cities) + date range
   - Stock: company/ticker keyword + date range
   - News: category keyword + topic keywords + date range

2. **Retrieve** — targeted MongoDB query (city + date, company + date, category + keyword regex). Falls back gracefully if exact match returns nothing.

3. **Augment** — `RAGService` formats the raw records into a plain-text context block (temperature max/min/mean, OHLCV fields, news title + summary).

4. **Generate** — `GeminiService` sends `system_prompt + context + question` to Gemini. The model is instructed to answer **only from the provided context**.

---

## Project Structure

```
backend/
├── app/
│   ├── config/
│   │   ├── database.py          # MongoDB Atlas connection
│   │   └── settings.py          # All env-var constants
│   ├── routers/
│   │   └── chat.py              # POST /api/chat endpoint
│   ├── schemas/
│   │   ├── chat_request.py      # Pydantic request model
│   │   └── chat_response.py     # Pydantic response model
│   ├── services/
│   │   ├── chat_service.py      # Dispatcher + chat history writer
│   │   ├── weather_service.py   # City + date extraction, MongoDB query
│   │   ├── stock_service.py     # Company + date extraction, MongoDB query
│   │   ├── news_service.py      # Keyword + date extraction, MongoDB query
│   │   ├── rag_service.py       # Context string builder
│   │   └── gemini_service.py    # Gemini API wrapper
│   ├── scripts/
│   │   ├── ingest_weather.py    # Fetch from Open-Meteo → MongoDB
│   │   ├── ingest_stock.py      # Fetch from Yahoo Finance → MongoDB
│   │   └── ingest_news.py       # Fetch from The Guardian → MongoDB
│   └── main.py                  # FastAPI app + CORS
├── run.py                       # uvicorn entry point
├── requirements.txt
└── .env

frontend/
├── src/
│   ├── components/
│   └── pages/
└── ...
```

---

## Historical Data Sources

### Weather — Open-Meteo Archive API
- **Source:** https://open-meteo.com (completely free, no API key)
- **Coverage:** 5 years (2020–2024), 10 major Indian cities
- **Cities:** Delhi, Mumbai, Chennai, Hyderabad, Bangalore, Kolkata, Pune, Ahmedabad, Jaipur, Lucknow
- **Fields:** `date`, `temperature` (mean/max/min), `humidity`, `wind_speed`, `rainfall_mm`, `condition`

### Stock — Yahoo Finance Chart API
- **Source:** Yahoo Finance (completely free, no API key)
- **Coverage:** 5 years (2020–2024), 15 NSE-listed companies
- **Companies:** Reliance, TCS, Infosys, HDFC Bank, ICICI Bank, Wipro, HCL Tech, Bajaj Finance, Kotak, HUL, SBI, ITC, Maruti Suzuki, Airtel, Sun Pharma
- **Fields:** `date`, `open`, `high`, `low`, `close`, `volume`, `change_percent`

### News — The Guardian Open Platform API
- **Source:** https://open-platform.theguardian.com (free developer key)
- **Coverage:** 2 years (2023–2024), India-filtered articles
- **Categories:** Politics, Economy, Business, Sports, Technology, Health, Environment, Entertainment
- **Fields:** `date`, `title`, `summary`, `category`, `source`, `tags`

---

## MongoDB Collections

| Collection | Purpose | Key Indexes |
|---|---|---|
| `weather_data` | Daily weather per city | `(city, date)` unique |
| `stock_data` | Daily OHLCV per company | `(company, date)` unique, `(symbol, date)` |
| `news_data` | News articles | `(date)`, `(category, date)` |
| `chat_history` | Every Q&A exchange | `(timestamp)` |

---

## API Reference

### `POST /api/chat`

**Request**
```json
{
  "mode": "weather",
  "question": "What was the temperature in Delhi on 15 June 2022?"
}
```

**Response**
```json
{
  "answer": "On 15 June 2022, Delhi recorded a mean temperature of 35.7°C, with a maximum of 39.6°C and a minimum of 31.2°C. Humidity was 62% and wind speed was 18.4 km/h."
}
```

**Valid modes:** `weather` | `stock` | `news`

**Sample questions per mode:**

| Mode | Example Question |
|---|---|
| weather | `What was the temperature in Mumbai in July 2021?` |
| weather | `Which Indian city was hottest in May 2023?` |
| stock | `What was the closing price of Infosys on 10 March 2023?` |
| stock | `How did Reliance Industries perform in January 2024?` |
| news | `What were the major economic news stories in India in March 2023?` |
| news | `What happened in Indian politics in November 2024?` |

---

## Setup & Run

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB Atlas account
- Google Gemini API key (free at https://aistudio.google.com)
- Guardian API key (free at https://open-platform.theguardian.com/access)

### 1. Clone and configure environment

```bash
# Copy the env template and fill in your keys
cd backend
```

Edit `backend/.env`:
```env
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/?appName=Cluster0
DATABASE_NAME=historical_rag
GEMINI_API_KEY=your_gemini_api_key
GUARDIAN_API_KEY=your_guardian_api_key
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Ingest historical data into MongoDB

Run each script once. They drop and recreate the collections.

```bash
# Weather: ~10 API calls, ~18,000 records (~30 seconds)
python -m app.scripts.ingest_weather

# Stock: ~15 API calls, ~15,000 records (~45 seconds)
python -m app.scripts.ingest_stock

# News: ~96 API calls, ~3,000 articles (~2 minutes)
python -m app.scripts.ingest_news
```

### 4. Start the backend

```bash
python run.py
# Server starts at http://localhost:8000
# Docs available at http://localhost:8000/docs
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
# App starts at http://localhost:5173
```

---

## Design Decisions

**No LangChain / no vector database** — RAG is implemented manually:
- Retrieval is MongoDB query-based (regex + date range), not embedding-based
- Context is a formatted plain-text string, not a vector
- Gemini receives only the retrieved slice of data, never the full collection

**Why this matters:** It demonstrates understanding of the RAG pattern at the code level rather than delegating it to a framework abstraction.

**Real data, not mocks** — all three collections are populated from live free APIs so queries return historically accurate answers.

---

## Author

**Md Sahbaz Alam**
