/**
 * API utility functions for Pojehat communication.
 */

const API_BASE = "http://localhost:8000/api/v1";

export async function uploadOEMManual(file: File, vehicleContext: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("vehicle_context", vehicleContext);

  const response = await fetch(`${API_BASE}/ingestion/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Failed to upload manual");
  }

  return response.json();
}

export async function ingestFromWeb(url: string, vehicleContext: string) {
  const response = await fetch(`${API_BASE}/ingestion/web`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url,
      vehicle_context: vehicleContext,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to start web ingestion");
  }

  return response.json();
}

export async function askMechanicAgent(query: string, vehicleContext: string) {
  const response = await fetch(`${API_BASE}/diagnostics/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query,
      vehicle_context: vehicleContext,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to query mechanic agent");
  }

  return response.json();
}
