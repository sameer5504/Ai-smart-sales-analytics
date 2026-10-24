import { createContext, useContext, useEffect, useState } from "react";

import { refreshAccessToken } from "../../features/auth/services/authService";
import {
    clearAccessToken as clearSessionAccessToken,
    getAccessToken,
    setAccessToken as setSessionAccessToken,
    subscribeToAuth,
} from "../auth/authSession";

const AuthContext = createContext(null);

let bootstrapPromise = null;

function bootstrapSession() {
    if (!bootstrapPromise) {
        bootstrapPromise = refreshAccessToken()
            .then((data) => {
                setSessionAccessToken(data.access_token);
            })
            .catch(() => {
                clearSessionAccessToken();
            });
    }

    return bootstrapPromise;
}

export function AuthProvider({ children }) {
    const [accessToken, setAccessTokenState] = useState(getAccessToken());

    const [isInitializing, setIsInitializing] = useState(true);

    useEffect(() => {
        return subscribeToAuth(setAccessTokenState);
    }, []);

    useEffect(() => {
        let active = true;

        bootstrapSession().finally(() => {
            if (active) {
                setIsInitializing(false);
            }
        });

        return () => {
            active = false;
        };
    }, []);

    const value = {
        accessToken,
        isAuthenticated: Boolean(accessToken),
        isInitializing,
        setAccessToken: setSessionAccessToken,
        clearAccessToken: clearSessionAccessToken,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const context = useContext(AuthContext);

    if (!context) {
        throw new Error("useAuth must be used inside AuthProvider");
    }

    return context;
}
