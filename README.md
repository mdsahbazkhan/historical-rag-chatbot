# Historical Multi-Domain RAG Chatbot

## Project Overview

The goal of this project was to build a single AI chatbot capable of answering questions about historical Weather, Stock Market, and News data.

Instead of relying entirely on an LLM's general knowledge, I implemented a Retrieval-Augmented Generation (RAG) approach where the chatbot first retrieves relevant historical records from MongoDB and then uses Gemini to generate a response based on that information.

---

## My Approach

One of the main challenges was handling multiple datasets without mixing information.

To solve this, I designed the chatbot with three modes:

* Weather
* Stock
* News

The selected mode determines which dataset is searched. For example, Weather queries only search weather data, while Stock and News queries remain completely independent.

This keeps retrieval accurate and makes the backend easier to maintain.

---

## Data Collection

I used free public APIs to collect historical data.

* Weather data was collected from Open-Meteo — covers **January 2021 to December 2025** for 10 major Indian cities.
* Stock market data was collected from Yahoo Finance — covers **January 2020 to December 2024** for 15 NSE-listed Indian companies.
* News articles were collected from The Guardian API — covers **January 2024 to December 2025** for India-related content.

The data is stored locally in MongoDB, allowing the chatbot to answer questions without making external API calls during conversations.

---

## RAG Workflow

The chatbot follows a simple RAG pipeline.

1. The user selects a mode and asks a question.
2. The corresponding service extracts important information such as city, company, category, keywords, and date.
3. MongoDB is searched for matching historical records.
4. The retrieved records are converted into context.
5. Gemini receives the context and the original question.
6. Gemini generates a natural language response based only on the retrieved data.

This approach helps reduce hallucinations and keeps answers grounded in stored historical information.

---

## Backend Design

I separated the backend into small services with specific responsibilities.

* Router handles HTTP requests.
* ChatService validates requests and routes them to the correct domain service.
* Weather, Stock, and News services handle domain-specific retrieval.
* RAGService prepares context from MongoDB records.
* GeminiService generates the final response.

This modular structure makes the project easier to understand and extend.

---

## Database

MongoDB stores four collections:

* weather_data
* stock_data
* news_data
* chat_history

Historical datasets are ingested once and reused for future queries.

---

## Key Design Decisions

Some decisions I made during development:

* Single chatbot instead of separate applications.
* Manual RAG implementation without LangChain.
* MongoDB-based retrieval instead of vector search.
* Separate services for different domains.
* Local historical storage to avoid repeated API calls.

---

## Challenges

Historical datasets may not contain information for every possible query.

Rather than generating unsupported answers, the chatbot reports when sufficient historical data is unavailable. This behaviour was intentional to improve reliability and reduce hallucinations.

---

## Technologies Used

* React
* FastAPI
* MongoDB Atlas
* Google Gemini
* Open-Meteo
* Yahoo Finance
* The Guardian API

---

## Author

Md Sahbaz Alam
