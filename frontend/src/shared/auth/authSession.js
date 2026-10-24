let accessToken = null;

const listeners = new Set();

export function getAccessToken() {
    return accessToken;
}

export function setAccessToken(token) {
    accessToken = token || null;

    listeners.forEach((listener) => {
        listener(accessToken);
    });
}

export function clearAccessToken() {
    setAccessToken(null);
}

export function subscribeToAuth(listener) {
    listeners.add(listener);

    listener(accessToken);

    return () => {
        listeners.delete(listener);
    };
}
