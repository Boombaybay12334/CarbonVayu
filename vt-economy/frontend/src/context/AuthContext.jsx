/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
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

async function ensureProfileExists(firebaseUser) {
  const fallbackProfile = {
    firebase_uid: firebaseUser.uid,
    email: firebaseUser.email ?? "",
    role: "common_man",
    state_name: null,
    state_id: null,
  };

  const { error } = await supabase
    .from("user_profiles")
    .upsert(fallbackProfile, { onConflict: "firebase_uid", ignoreDuplicates: true });

  if (error) {
    throw error;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadOrRecoverProfile = useCallback(async (firebaseUser) => {
    const loadedProfile = await fetchProfileWithRetry(firebaseUser.uid);
    if (loadedProfile) {
      return loadedProfile;
    }

    // Self-heal legacy accounts that were created without a profile row.
    await ensureProfileExists(firebaseUser);
    return fetchProfileWithRetry(firebaseUser.uid);
  }, []);

  const refreshProfile = useCallback(async () => {
    const firebaseUser = auth.currentUser;
    if (!firebaseUser) {
      setUser(null);
      setProfile(null);
      return;
    }

    setLoading(true);
    try {
      const loadedProfile = await loadOrRecoverProfile(firebaseUser);
      setUser(firebaseUser);
      setProfile(loadedProfile ?? null);
    } catch (error) {
      console.error("Failed to refresh user profile", error);
      setUser(firebaseUser);
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, [loadOrRecoverProfile]);

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
          const loadedProfile = await loadOrRecoverProfile(firebaseUser);

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
  }, [loadOrRecoverProfile]);

  const logout = () => signOut(auth);

  return (
    <AuthContext.Provider value={{ user, profile, loading, logout, refreshProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
