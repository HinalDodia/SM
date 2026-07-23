// In production, set VITE_API_URL in your hosting env (e.g. Vercel, Netlify, EC2).
// In development, it falls back to http://localhost:5000.
export const API_BASE_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "https://y45by36cancgoh6smeifazwmsy0dufxi.lambda-url.ap-south-1.on.aws";

// API_URL is kept as an alias for backward compatibility —
// many components import { API_URL } from "./config".
export const API_URL = API_BASE_URL;