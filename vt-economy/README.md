# VT Economy - Vaayu Token Platform

VT Economy is a React web app scaffold to visualize and govern the Vaayu Token (VT) economy for Indian states.

## Architecture
- Frontend: React 18 + Vite + Tailwind CSS
- Routing: React Router v6
- Auth: Firebase Auth (JS SDK v9 modular API)
- Data: Supabase via `@supabase/supabase-js`
- Charts: Recharts
- Backend: none (Firebase + Supabase only)

## Setup
1. Clone the repository.
2. Copy `.env.example` to `.env` and fill all Firebase + Supabase values.
3. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```
4. Start development server:
   ```bash
   npm run dev
   ```

## Firebase Setup
See [docs/FIREBASE_SETUP.md](docs/FIREBASE_SETUP.md).

## Supabase Setup
See [docs/SUPABASE_SCHEMA.md](docs/SUPABASE_SCHEMA.md).

## For Teammates
- Branching convention:
  - `feat/<module-name>` for features
  - `fix/<module-name>` for bug fixes
  - `docs/<topic>` for documentation updates
- Edit scope:
  - Routing only in `frontend/src/App.jsx`
  - Supabase query logic only in `frontend/src/services/*`
  - Shared placeholders and fake records only in `frontend/src/dummy/dummyData.js`
- Dummy data rules:
  - Keep all fake data centralized in `dummyData.js`
  - Use `// DUMMY DATA - replace with Supabase query` where applicable
- Task completion checklist:
  - Replace one service function at a time with a real Supabase query
  - Verify corresponding page renders without errors
  - Update `docs/DUMMY_DATA_GUIDE.md` and `docs/API_REFERENCE.md`


OH CAPTAIN MY CAPTAIN
