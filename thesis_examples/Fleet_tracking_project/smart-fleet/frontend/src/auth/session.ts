import keycloak from "../keycloak";

// Μοιραζόμαστε την ίδια ανανέωση όταν συμπίπτουν περισσότερες ενέργειες.
let tokenRefresh: Promise<void> | null = null;
let sessionHasExpired = false;

export function readAccessToken(): string {
    if (typeof keycloak.token === "string") {
        return keycloak.token;
    }

    return "";
}

export function isSessionExpired(): boolean {
    if (sessionHasExpired) return true;
    if (readAccessToken() === "") return true;

    return keycloak.isTokenExpired(0);
}

export function expireSession() {
    if (sessionHasExpired) return;

    sessionHasExpired = true;
    window.dispatchEvent(new Event("session-expired"));
}

export function refreshTokenForUserAction(): Promise<void> {
    // Μια ενέργεια που συμπίπτει με υπάρχουσα ανανέωση περιμένει το αποτέλεσμά της.
    if (tokenRefresh !== null) {
        return tokenRefresh;
    }

    // Μετά τη λήξη λόγω αδράνειας απαιτείται νέα σύνδεση.
    if (isSessionExpired()) {
        expireSession();
        return Promise.reject(new Error("Session expired. Please sign in again."));
    }

    // Το -1 ζητά νέο token ακόμη κι αν το προηγούμενο δεν πλησιάζει στη λήξη.
    tokenRefresh = keycloak.updateToken(-1)
        .then(() => {
            if (readAccessToken() === "") {
                throw new Error("Keycloak did not return an access token.");
            }

            window.dispatchEvent(new Event("session-token-updated"));
        })
        .catch((error: unknown) => {
            if (isSessionExpired()) {
                expireSession();
            }

            throw error;
        })
        .finally(() => {
            tokenRefresh = null;
        });

    return tokenRefresh;
}

export function handleTokenExpiration() {
    // Αν η ανανέωση ξεκίνησε εγκαίρως, περιμένουμε την απάντησή της.
    if (tokenRefresh !== null) return;

    expireSession();
}

export async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
    // Τα requests δεν ανανεώνουν από μόνα τους τη συνεδρία.
    // Περιμένουν μόνο ανανέωση που ξεκίνησε από ενέργεια χρήστη.
    if (tokenRefresh !== null) {
        await tokenRefresh;
    }

    if (isSessionExpired()) {
        expireSession();
        throw new Error("Session expired. Please sign in again.");
    }

    // Αντικαθιστούμε τυχόν παλιό Authorization με το τρέχον token.
    const headers = new Headers(options.headers);
    headers.set("Authorization", `Bearer ${readAccessToken()}`);

    return window.fetch(url, { ...options, headers });
}