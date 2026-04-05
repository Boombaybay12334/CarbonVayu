# Firebase Setup

1. Go to `https://console.firebase.google.com` and create a new project.
2. Open the project and click **Build > Authentication**.
3. Enable **Email/Password** in Sign-in method.
4. Go to **Project settings > General > Your apps** and register a web app.
5. Copy the Firebase config values into `.env`:
   - `VITE_FIREBASE_API_KEY`
   - `VITE_FIREBASE_AUTH_DOMAIN`
   - `VITE_FIREBASE_PROJECT_ID`
   - `VITE_FIREBASE_STORAGE_BUCKET`
   - `VITE_FIREBASE_MESSAGING_SENDER_ID`
   - `VITE_FIREBASE_APP_ID`
6. Create one test user per role (`common_man`, `state`, `admin`) using either:
   - Firebase Console -> Authentication -> Users -> Add user, or
   - App signup flow.
7. Ensure each Firebase user has a matching row in Supabase `user_profiles`.

## Note
Firebase stores identity only. Roles and state mappings are stored in Supabase `user_profiles` keyed by `firebase_uid`.
