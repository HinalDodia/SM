import React, { createContext, useState, useEffect } from "react";
import { toast } from "react-toastify";

export const UserContext = createContext({
  user: null,
  setUser: () => {}
});

export const UserProvider = ({ children }) => {
  const [user, setUserState] = useState(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("user");
      if (raw) setUserState(JSON.parse(raw));
    } catch {}
  }, []);

  const setUser = (u) => {
    try {
      if (u) {
        localStorage.setItem("user", JSON.stringify(u));
        const name = u.name || u.email || "User";
        toast.info(`Hi, ${name}`, { autoClose: 2500 });
      } else {
        localStorage.removeItem("user");
        localStorage.removeItem("id_token");
      }
    } catch {}
    setUserState(u);
  };

  return (
    <UserContext.Provider value={{ user, setUser }}>
      {children}
    </UserContext.Provider>
  );
};
