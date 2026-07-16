// src/firebase.jsx
import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup  } from "firebase/auth";
import { getAnalytics } from "firebase/analytics";

const firebaseConfig = {
  apiKey: "AIzaSyDOFkleEgowIDUXPOHczOuBUY1FS_OUiIQ",
  authDomain: "finwise-cfa37.firebaseapp.com",
  projectId: "finwise-cfa37",
  storageBucket: "finwise-cfa37.appspot.com",
  messagingSenderId: "813880104994",
  appId: "1:813880104994:web:4730242ba640d5f5c8527b",
  measurementId: "G-83ZH8NW93T",
};

const app = initializeApp(firebaseConfig);

let analytics = null;
try {
  analytics = getAnalytics(app);
} catch (e) {
  // ok in dev if analytics can't initialize
  // console.warn("Analytics not initialized:", e.message);
}

const auth = getAuth(app);
const provider = new GoogleAuthProvider();
export async function signInWithGooglePopup() {
  const result = await signInWithPopup(auth, provider);
  const idToken = await result.user.getIdToken();
  return idToken;
}
export { auth, provider, analytics };
