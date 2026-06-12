import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 30000,
});

export const sendMessage = async (mode, question) => {
  const response = await api.post("/api/chat", { mode, question });
  return response.data;
};

export default api;
