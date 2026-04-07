/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from "react";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { auth } from "../lib/firebase";
import { supabase } from "../lib/supabase";

const AuthContext = createContext(null);
const PROFILE_FETCH_ATTEMPTS = 6;
const PROFILE_FETCH_BASE_DELAY_MS = 250;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchProfileWithRetry(firebaseUid) {
  for (let attempt = 1; attempt <= PROFILE_FETCH_ATTEMPTS; attempt += 1) {
    const { data, error } = await supabase
      .from("user_profiles")
      .select("role, state_name, state_id")
      .eq("firebase_uid", firebaseUid)
      .maybeSingle();

    if (error) {
      throw error;
    }

    if (data) {
      return data;
    }

    if (attempt < PROFILE_FETCH_ATTEMPTS) {
      await wait(PROFILE_FETCH_BASE_DELAY_MS * attempt);
    }
  }

  return null;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isActive = true;
    let latestRequestId = 0;

    const unsub = onAuthStateChanged(auth, async (firebaseUser) => {
      const requestId = latestRequestId + 1;
      latestRequestId = requestId;

      if (isActive) {
        setLoading(true);
      }

      try {
        if (firebaseUser) {
          const loadedProfile = await fetchProfileWithRetry(firebaseUser.uid);

          if (isActive && requestId === latestRequestId) {
            setUser(firebaseUser);
            setProfile(loadedProfile ?? null);
          }
        } else {
          if (isActive && requestId === latestRequestId) {
            setUser(null);
            setProfile(null);
          }
        }
      } catch (error) {
        console.error("Failed to load user profile", error);
        if (isActive && requestId === latestRequestId) {
          setUser(firebaseUser ?? null);
          setProfile(null);
        }
      } finally {
        if (isActive && requestId === latestRequestId) {
          setLoading(false);
        }
      }
    });

    return () => {
      isActive = false;
      unsub();
    };
  }, []);

  const logout = () => signOut(auth);

  return (
    <AuthContext.Provider value={{ user, profile, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
