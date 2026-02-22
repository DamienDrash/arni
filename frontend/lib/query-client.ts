import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 30_000,        // 30s — daten gelten als frisch
            gcTime: 5 * 60_000,       // 5min — cache garbage collection
            retry: 1,                 // 1 retry bei Netz-Fehler
            refetchOnWindowFocus: false,
        },
        mutations: {
            retry: 0,
        },
    },
});
