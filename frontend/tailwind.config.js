/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['var(--font-heading)', 'sans-serif'],
                mono: ['var(--font-mono)', 'monospace'],
            },
            colors: {
                // Custom palette from the Inntegrate reference
                inntegrate: {
                    sidebar: "#11142D",
                    canvas: "#F7F7F7",
                    card: "#FFFFFF",
                    primary: "#6C5DD3",
                    text: "#1B1D21",
                    muted: "#808191",
                }
            }
        },
    },
};
