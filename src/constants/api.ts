import { Platform } from "react-native";

export const apiBaseUrl = (
  process.env.EXPO_PUBLIC_API_URL ||
  (Platform.OS === "web" ? "http://localhost:5000" : "http://192.168.100.42:5000")
).replace(/\/$/, "");
