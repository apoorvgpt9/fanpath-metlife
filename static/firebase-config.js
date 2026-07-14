// Public Firebase web config. apiKey is a client-side identifier, not a
// secret (per Firebase docs) — quotas and per-project rules restrict abuse.
// Swap the placeholder apiKey below with the real one from the Firebase
// console before serving; project_id + authDomain are the deployed values.
window.FIREBASE_CONFIG = {
  apiKey: "REPLACE_WITH_FIREBASE_WEB_API_KEY",
  authDomain: "promptwars-c4-metlife.firebaseapp.com",
  projectId: "promptwars-c4-metlife",
};
